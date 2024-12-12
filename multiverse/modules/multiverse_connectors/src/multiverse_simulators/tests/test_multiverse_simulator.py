#!/usr/bin/env python3

import time
import unittest
from typing import Optional, Tuple

import numpy

from multiverse_simulator import MultiverseSimulator, MultiverseSimulatorState, MultiverseSimulatorConstraints, \
    MultiverseSimulatorStopReason, MultiverseViewer, MultiverseAttribute


class MultiverseSimulatorTestCase(unittest.TestCase):
    file_path: str = ""
    headless: bool = False
    real_time_factor: float = 1.0
    step_size: float = 1E-3
    Simulator = MultiverseSimulator

    def test_initialize_multiverse_simulator(self, viewer: Optional[MultiverseViewer] = None) -> MultiverseSimulator:
        simulator = self.Simulator(viewer=viewer,
                                   file_path=self.file_path,
                                   headless=self.headless,
                                   real_time_factor=self.real_time_factor,
                                   step_size=self.step_size)
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)
        self.assertIs(simulator.headless, self.headless)
        self.assertEqual(simulator.real_time_factor, self.real_time_factor)
        self.assertIsNone(simulator.stop_reason)
        self.assertIsNone(simulator.simulation_thread)
        return simulator

    def test_initialize_multiverse_viewer(self,
                                          send_objects: Optional = None,
                                          receive_objects: Optional = None,
                                          number_of_instances=2) -> MultiverseViewer:
        if send_objects is None:
            send_attrs = {
                "cmd_joint_rvalue": MultiverseAttribute(default_value=numpy.array([1])),
                "cmd_joint_angular_velocity": MultiverseAttribute(default_value=numpy.array([2]))
            }
            send_objects = {
                "actuator1": send_attrs,
                "actuator2": send_attrs,
            }
        if receive_objects is None:
            receive_attrs = {
                "joint_rvalue": MultiverseAttribute(default_value=numpy.array([1])),
                "joint_angular_velocity": MultiverseAttribute(default_value=numpy.array([2]))
            }
            receive_objects = {
                "joint1": receive_attrs,
                "joint2": receive_attrs,
            }
        viewer = MultiverseViewer(send_objects=send_objects, receive_objects=receive_objects)
        viewer.initialize_data(number_of_instances=number_of_instances)
        self.assertEqual(viewer.send_objects, send_objects)
        self.assertEqual(viewer.receive_objects, receive_objects)

        send_data = numpy.array([[i for attrs in send_objects.values()
                                  for attr in attrs.values() for i in attr.default_value] for _ in
                                 range(number_of_instances)])
        receive_data = numpy.array([[i for attrs in receive_objects.values()
                                     for attr in attrs.values() for i in attr.default_value] for _ in
                                    range(number_of_instances)])
        self.assertTrue(numpy.array_equal(viewer.send_data, send_data))
        self.assertTrue(numpy.array_equal(viewer.receive_data, receive_data))
        return viewer

    def test_initialize_multiverse_with_viewer(self) -> Tuple[MultiverseSimulator, MultiverseViewer]:
        viewer = self.test_initialize_multiverse_viewer()
        simulator = self.test_initialize_multiverse_simulator(viewer=viewer)
        self.assertEqual(simulator._viewer, viewer)
        return simulator, viewer

    def test_start_and_stop_multiverse_simulator(self) -> MultiverseSimulator:
        simulator = self.test_initialize_multiverse_simulator()
        simulator.start()
        self.assertIs(simulator.state, MultiverseSimulatorState.RUNNING)
        simulator.stop()
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)
        self.assertIs(simulator.stop_reason, MultiverseSimulatorStopReason.STOP)
        self.assertFalse(simulator.renderer.is_running())
        self.assertFalse(simulator.simulation_thread.is_alive())
        return simulator

    def test_pause_and_unpause_multiverse_simulator(self) -> MultiverseSimulator:
        simulator = self.test_start_and_stop_multiverse_simulator()
        simulator.pause()
        simulator.start()
        self.assertIs(simulator.state, MultiverseSimulatorState.RUNNING)
        for _ in range(10):
            simulator.pause()
            self.assertIs(simulator.state, MultiverseSimulatorState.PAUSED)
            simulator.unpause()
            self.assertIs(simulator.state, MultiverseSimulatorState.RUNNING)
        simulator.unpause()
        self.assertIs(simulator.state, MultiverseSimulatorState.RUNNING)
        simulator.stop()
        return simulator

    def test_step_multiverse_simulator(self) -> MultiverseSimulator:
        simulator = self.test_pause_and_unpause_multiverse_simulator()
        simulator.start(run_in_thread=False)
        self.assertIsNone(simulator.stop_reason)
        for i in range(10):
            self.assertIs(simulator.current_number_of_steps, i)
            if (simulator.current_simulation_time - i * simulator.step_size) > 1E-6:
                print(simulator.current_simulation_time, i * simulator.step_size)
            self.assertAlmostEqual(simulator.current_simulation_time, i * simulator.step_size)
            simulator.step()
            self.assertIsNone(simulator.stop_reason)
        simulator.stop()
        self.assertIs(simulator.stop_reason, MultiverseSimulatorStopReason.STOP)
        self.assertFalse(simulator.simulation_thread.is_alive())
        return simulator

    def test_reset_multiverse_simulator(self) -> MultiverseSimulator:
        simulator = self.test_initialize_multiverse_simulator()
        simulator.start(run_in_thread=False)
        simulator.reset()
        self.assertEqual(simulator.current_number_of_steps, 0)
        self.assertEqual(simulator.current_simulation_time, 0.0)
        simulator.stop()
        self.assertIs(simulator.stop_reason, MultiverseSimulatorStopReason.STOP)
        return simulator

    def test_run_with_constraints_multiverse_simulator(self,
                                                       constraints: Optional[
                                                           MultiverseSimulatorConstraints] = None) -> MultiverseSimulator:
        simulator = self.test_initialize_multiverse_simulator()
        simulator.start(constraints=constraints)
        while simulator.state == MultiverseSimulatorState.RUNNING:
            if constraints is None:
                simulator.renderer.close()
            else:
                if constraints.max_number_of_steps is not None and simulator.current_number_of_steps > constraints.max_number_of_steps + 10:
                    raise Exception("Constraints max_number_of_steps are not working")
                if constraints.max_simulation_time is not None and simulator.current_simulation_time > constraints.max_simulation_time + 10 * simulator.step_size:
                    raise Exception("Constraints max_simulation_time are not working")
                if constraints.max_real_time is not None and simulator.current_real_time - simulator.start_real_time > constraints.max_real_time + 1.0:
                    raise Exception("Constraints max_real_time are not working")
        if constraints is None:
            self.assertEqual(simulator.stop_reason, MultiverseSimulatorStopReason.VIEWER_IS_CLOSED)
        else:
            if constraints.max_number_of_steps is not None:
                self.assertLessEqual(simulator.current_number_of_steps, constraints.max_number_of_steps)
            if constraints.max_simulation_time is not None:
                self.assertLessEqual(simulator.current_simulation_time,
                                     constraints.max_simulation_time + simulator.step_size)
            if constraints.max_real_time is not None:
                self.assertLessEqual(simulator.current_real_time - simulator.start_real_time,
                                     constraints.max_real_time + 1.0)
            self.assertIsNotNone(simulator.stop_reason)

        return simulator

    def test_run_with_multiple_constraints_multiverse_simulator(self) -> MultiverseSimulator:
        max_number_of_steps = 10
        constraints = MultiverseSimulatorConstraints(max_number_of_steps=max_number_of_steps)
        simulator = self.test_run_with_constraints_multiverse_simulator(constraints=constraints)
        self.assertIs(simulator.current_number_of_steps, max_number_of_steps)
        self.assertIs(simulator.stop_reason, MultiverseSimulatorStopReason.MAX_NUMBER_OF_STEPS)

        max_simulation_time = 0.01
        constraints = MultiverseSimulatorConstraints(max_simulation_time=max_simulation_time)
        simulator = self.test_run_with_constraints_multiverse_simulator(constraints=constraints)
        self.assertAlmostEqual(simulator.current_simulation_time, max_simulation_time)

        max_real_time = 0.1
        constraints = MultiverseSimulatorConstraints(max_real_time=max_real_time)
        simulator = self.test_run_with_constraints_multiverse_simulator(constraints=constraints)
        self.assertLessEqual(simulator.current_real_time - simulator.start_real_time, max_real_time + 1.0)

        constraints = MultiverseSimulatorConstraints(max_number_of_steps=max_number_of_steps,
                                                     max_simulation_time=max_simulation_time,
                                                     max_real_time=max_real_time)
        simulator = self.test_run_with_constraints_multiverse_simulator(constraints=constraints)
        self.assertIsNotNone(simulator.stop_reason)

        return simulator

    def test_real_time(self):
        self.step_size = 1E-4
        simulator = self.test_initialize_multiverse_simulator()
        constraints = MultiverseSimulatorConstraints(max_real_time=1.0)
        simulator.start(constraints=constraints)
        while simulator.state == MultiverseSimulatorState.RUNNING:
            time.sleep(1)
        self.assertIs(simulator.state, MultiverseSimulatorState.STOPPED)


if __name__ == '__main__':
    unittest.main()
