import os
import time
import unittest
import xml.etree.ElementTree as ET

import mujoco
import mujoco.viewer
import numpy

from mujoco_connector import MultiverseMujocoConnector
from multiverse_simulator import MultiverseSimulatorConstraints, MultiverseSimulatorState, MultiverseViewer, \
    MultiverseFunctionResult
from test_multiverse_simulator import MultiverseSimulatorTestCase

resources_path = os.path.join(os.path.dirname(__file__), "..", "resources")


# @unittest.skip("This test is not meant to be run in CI")
class MultiverseMujocoConnectorBaseTestCase(MultiverseSimulatorTestCase):
    file_path = os.path.join(resources_path, "mjcf/floor/floor.xml")
    Simulator = MultiverseMujocoConnector
    headless = False
    step_size = 1E-3
    use_mjx = False

    def test_functions(self):
        copy_file = os.path.join(resources_path, "saved", "mjx_single_cube.xml")
        simulator = self.Simulator(file_path=os.path.join(resources_path, "mjcf/mujoco_menagerie/franka_emika_panda/mjx_single_cube_test.xml"))
        simulator.start(run_in_thread=False)

        for step in range(10000):
            if step == 100:
                result = simulator.get_all_body_names()
                self.assertIsInstance(result, MultiverseFunctionResult)
                self.assertEqual(result.type, MultiverseFunctionResult.ResultType.SUCCESS_WITHOUT_EXECUTION)
                self.assertEqual(result.result, ['world', 'link0', 'link1', 'link2', 'link3', 'link4',
                                                 'link5', 'link6', 'link7', 'hand', 'left_finger',
                                                 'right_finger', 'box', 'mocap_target'])

                result = simulator.get_all_joint_names()
                self.assertIsInstance(result, MultiverseFunctionResult)
                self.assertEqual(result.type, MultiverseFunctionResult.ResultType.SUCCESS_WITHOUT_EXECUTION)
                self.assertEqual(result.result, ['joint1', 'joint2', 'joint3', 'joint4', 'joint5',
                                                 'joint6', 'joint7', 'finger_joint1', 'finger_joint2', ''])

                result = simulator.attach("abc")
                self.assertEqual(MultiverseFunctionResult.ResultType.FAILURE_BEFORE_EXECUTION_ON_MODEL, result.type)
                self.assertEqual("Body 1 abc not found", result.info)

                result = simulator.attach("world")
                self.assertEqual(MultiverseFunctionResult.ResultType.FAILURE_BEFORE_EXECUTION_ON_MODEL, result.type)
                self.assertEqual("Body 1 and body 2 are the same", result.info)

                result = simulator.attach("box")
                self.assertEqual(MultiverseFunctionResult.ResultType.SUCCESS_WITHOUT_EXECUTION, result.type)
                self.assertEqual("Body 1 box is already attached to body 2 world", result.info)

                result = simulator.attach("box", "hand")
                self.assertEqual(MultiverseFunctionResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_MODEL, result.type)
                self.assertEqual("Attached body 1 box to body 2 hand "
                                 "at relative position [0.5  0.   0.03], relative quaternion [1. 0. 0. 0.]", result.info)
            simulator.step()
            simulator.run_callback()
            time.sleep(0.001)


class MultiverseMujocoConnectorHeadlessBaseTestCase(MultiverseMujocoConnectorBaseTestCase):
    file_path = os.path.join(resources_path, "mjcf/floor/floor.xml")
    Simulator = MultiverseMujocoConnector
    headless = True
    step_size = 1E-3
    use_mjx = False


@unittest.skip("This test is not meant to be run in CI")
class MultiverseMujocoConnectorComplexTestCase(MultiverseMujocoConnectorBaseTestCase):
    file_path = os.path.join(resources_path, "mjcf/mujoco_menagerie/franka_emika_panda/mjx_single_cube.xml")
    Simulator = MultiverseMujocoConnector
    headless = False
    step_size = 5E-4

    def test_running_in_10s(self):
        simulator = self.test_initialize_multiverse_simulator()
        constraints = MultiverseSimulatorConstraints(max_real_time=10.0)
        simulator.start(constraints=constraints)
        while simulator.state != MultiverseSimulatorState.STOPPED:
            time.sleep(1)
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)

    def test_running_in_10s_with_viewer(self):
        write_objects = {
            "actuator1": {
                "cmd_joint_rvalue": [0.0]
            },
            "actuator2": {
                "cmd_joint_rvalue": [0.0]
            },
        }
        read_objects = {
            "joint1": {
                "joint_rvalue": [0.0],
                "joint_angular_velocity": [0.0]
            },
            "joint2": {
                "joint_rvalue": [0.0],
                "joint_angular_velocity": [0.0]
            },
            "actuator1": {
                "cmd_joint_rvalue": [0.0]
            },
            "actuator2": {
                "cmd_joint_rvalue": [0.0]
            }
        }
        viewer = MultiverseViewer(write_objects=write_objects, read_objects=read_objects)
        simulator = self.test_initialize_multiverse_simulator(viewer=viewer)
        constraints = MultiverseSimulatorConstraints(max_simulation_time=10.0)
        simulator.start(constraints=constraints)
        use_write_data = True
        while simulator.state != MultiverseSimulatorState.STOPPED:
            time_now = time.time()
            f = 0.5
            act_1_value = numpy.pi / 6 * numpy.sin(2.0 * numpy.pi * f * time_now)
            act_2_value = numpy.pi / 6 * numpy.sin(-1.0 * numpy.pi * f * time_now)
            if use_write_data:
                viewer.write_data = numpy.array([[act_1_value, act_2_value]])
            else:
                viewer.write_objects["actuator1"]["cmd_joint_rvalue"].values[0][0] = act_1_value
                viewer.write_objects["actuator2"]["cmd_joint_rvalue"].values[0][0] = act_2_value
            use_write_data = not use_write_data
            time.sleep(0.01)
            self.assertEqual(viewer.read_data.shape, (1, 6))
            if simulator.current_simulation_time > 1.0:
                self.assertAlmostEqual(viewer.read_objects["joint1"]["joint_rvalue"].values[0][0], act_1_value,
                                       places=0)
                self.assertAlmostEqual(viewer.read_objects["joint2"]["joint_rvalue"].values[0][0], act_2_value,
                                       places=0)
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)

    def test_read_and_write_data_in_the_loop(self):
        viewer = MultiverseViewer()
        simulator = self.test_initialize_multiverse_simulator(viewer=viewer)
        simulator.start(run_in_thread=False)
        for step in range(10000):
            if step == 100:
                read_objects = {
                    "joint1": {
                        "joint_rvalue": [0.0],
                        "joint_angular_velocity": [0.0]
                    },
                    "joint2": {
                        "joint_rvalue": [0.0],
                        "joint_angular_velocity": [0.0]
                    }
                }
                viewer.read_objects = read_objects
            elif step == 101:
                read_objects = {
                    "joint1": {
                        "joint_angular_velocity": [0.0]
                    },
                    "joint2": {
                        "joint_rvalue": [0.0],
                        "joint_torque": [0.0]
                    }
                }
                viewer.read_objects = read_objects
            elif step == 102:
                write_objects = {
                    "joint1": {
                        "joint_rvalue": [1.0]
                    },
                    "actuator2": {
                        "cmd_joint_rvalue": [2.0]
                    },
                }
                read_objects = {
                    "joint1": {
                        "joint_rvalue": [0.0],
                        "joint_angular_velocity": [0.0]
                    },
                    "actuator2": {
                        "cmd_joint_rvalue": [0.0]
                    }
                }
                viewer.write_objects = write_objects
                viewer.read_objects = read_objects
            else:
                viewer.read_objects = {}
            simulator.step()
            if step == 100:
                self.assertEqual(viewer.read_data.shape, (1, 4))
                self.assertEqual(viewer.read_objects["joint1"]["joint_rvalue"].values.shape, (1, 1))
                self.assertEqual(viewer.read_objects["joint2"]["joint_rvalue"].values.shape, (1, 1))
                self.assertEqual(viewer.read_objects["joint1"]["joint_angular_velocity"].values.shape, (1, 1))
                self.assertEqual(viewer.read_objects["joint2"]["joint_angular_velocity"].values.shape, (1, 1))
            elif step == 101:
                self.assertEqual(viewer.read_data.shape, (1, 3))
                self.assertEqual(viewer.read_objects["joint1"]["joint_angular_velocity"].values.shape, (1, 1))
                self.assertEqual(viewer.read_objects["joint2"]["joint_rvalue"].values.shape, (1, 1))
                self.assertEqual(viewer.read_objects["joint2"]["joint_torque"].values.shape, (1, 1))
            elif step == 102:
                self.assertEqual(viewer.write_data.shape, (1, 2))
                self.assertEqual(viewer.write_objects["joint1"]["joint_rvalue"].values[0], (1.0,))
                self.assertEqual(viewer.write_objects["actuator2"]["cmd_joint_rvalue"].values[0], (2.0,))
                self.assertEqual(viewer.read_data.shape, (1, 3))
                self.assertAlmostEqual(viewer.read_objects["joint1"]["joint_rvalue"].values[0][0], 1.0, places=3)
                self.assertEqual(viewer.read_objects["actuator2"]["cmd_joint_rvalue"].values[0][0], 2.0)
            else:
                self.assertEqual(viewer.read_data.shape, (1, 0))
        simulator.stop()
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)

    def test_running_with_mjx_in_10s(self):
        simulator = MultiverseMujocoConnector(file_path=os.path.join(resources_path, "mjcf/unitree/h1_scene.xml"),
                                              use_mjx=True,
                                              headless=False,
                                              real_time_factor=-1,
                                              step_size=0.001)
        constraints = MultiverseSimulatorConstraints(max_simulation_time=10.0)
        simulator.start(constraints=constraints)
        while simulator.state != MultiverseSimulatorState.STOPPED:
            time.sleep(1)
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)


@unittest.skip("This test is not meant to be run in CI")
class MujocoSpeedTestCase(unittest.TestCase):
    file_path = os.path.join(resources_path, "mjcf/mujoco_menagerie/franka_emika_panda/mjx_single_cube.xml")
    step_size = 5E-4
    real_time_factor = 1.0
    lib_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "build", "mujoco", "lib",
                            "libmultiverse_connector.so")
    include_extension = """
    <extension>
        <plugin plugin="mujoco.multiverse_connector">
              <instance name="mujoco_client">
                    <config key="host" value="tcp://127.0.0.1"/>
                    <config key="server_port" value="7000"/>
                    <config key="client_port" value="7500"/>
                    <config key="world_name" value="world"/>
                    <config key="simulation_name" value="mujoco_sim"/>
                    <config key="send" value="{'world': ['position', 'quaternion']}" />
              </instance>
        </plugin>
    </extension>
    """

    def test_running_speed(self):
        m = mujoco.MjModel.from_xml_path(self.file_path)
        m.opt.timestep = self.step_size
        d = mujoco.MjData(m)
        with mujoco.viewer.launch_passive(m, d) as viewer:
            time_now = time.time()
            start_real_time = time.time()
            while viewer.is_running():
                real_time_pass = time.time() - start_real_time
                simulation_time_pass = d.time * self.real_time_factor
                delta_time = simulation_time_pass - real_time_pass
                if delta_time <= self.step_size:
                    mujoco.mj_step(m, d)
                if delta_time > self.step_size * 10:
                    print(
                        f"Real time is {delta_time} seconds ({delta_time / self.step_size} step_size) behind simulation time")
                elif delta_time < -self.step_size * 10:
                    print(
                        f"Real time is {-delta_time} seconds ({-delta_time / self.step_size} step_size) ahead of simulation time")
                if time.time() - time_now > 1.0 / 60.0:
                    viewer.sync()
                    time_now = time.time()

    def test_running_with_multiverse(self):
        """
        This test must be run with 'multiverse_server' running
        """
        mujoco.mj_loadPluginLibrary(self.lib_path)
        file_xml = ET.parse(os.path.join(resources_path, "mjcf/floor/floor.xml"))
        root = file_xml.getroot()
        root.append(ET.fromstring(self.include_extension))
        file_xml_string = ET.tostring(root, encoding='unicode', method='xml')
        m = mujoco.MjModel.from_xml_string(file_xml_string)
        self.assertIsNotNone(m)
        d = mujoco.MjData(m)
        self.assertEqual(d.time, 0.0)


if __name__ == '__main__':
    unittest.main()
