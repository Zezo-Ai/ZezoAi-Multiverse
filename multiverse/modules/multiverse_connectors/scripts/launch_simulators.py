#!/usr/bin/env python3.10

import re
import subprocess
from typing import List, Dict, Any

from multiverse_launch import MultiverseLaunch
from utils import find_files, run_subprocess


def parse_mujoco(resources_paths: List[str], mujoco_data: Dict[str, Any]):
    worlds_path = find_files(resources_paths, mujoco_data["world"]["path"])
    mujoco_args = [f"--world={worlds_path}"]

    for entity_str in ["robots", "objects"]:
        if entity_str in mujoco_data:
            for entity_name in mujoco_data[entity_str]:
                if "path" in mujoco_data[entity_str][entity_name]:
                    mujoco_data[entity_str][entity_name]["path"] = find_files(resources_paths,
                                                                              mujoco_data[entity_str][entity_name][
                                                                                  "path"])
            entity_dict = mujoco_data[entity_str]
            mujoco_args.append(f"--{entity_str}={entity_dict}".replace(" ", ""))

    return mujoco_args


class MultiverseSimulationLaunch(MultiverseLaunch):
    simulators = {"mujoco"}

    def __init__(self):
        super().__init__()

    def run_simulations(self) -> List[subprocess.Popen]:
        processes: List[subprocess.Popen] = []
        for simulation_name, simulation_data in self.simulations.items():
            if "simulator" not in simulation_data or simulation_data["simulator"] not in self.simulators:
                continue

            result = self.run_simulator_compile(simulation_name, simulation_data)
            processes.append(self.run_simulator(result, simulation_name, simulation_data))
        return processes

    def parse_simulator(self, simulation_data):
        if simulation_data["simulator"] == "mujoco":
            return parse_mujoco(self.resources_paths, simulation_data)
        else:
            raise NotImplementedError(f"Simulator {simulation_data['simulator']} not implemented")

    def run_simulator_compile(self, simulation_name, simulation_data):
        cmd = self.parse_simulator(simulation_data)
        cmd = [f"{simulation_data['simulator']}_compile", f"--name={simulation_name}"] + cmd
        cmd_str = " ".join(cmd)
        print(f'Execute "{cmd_str}"')
        return subprocess.run(cmd, capture_output=True, text=True)

    def run_simulator(self, compiler_result: subprocess.CompletedProcess, simulation_name,
                      simulation_data) -> subprocess.Popen:
        if compiler_result.returncode != 0:
            print(compiler_result.stderr)
            raise RuntimeError(f"Failed to compile {simulation_name}")

        scene_xml_path = re.search(r"Scene:\s*([^\n]+)", compiler_result.stdout).group(1)
        cmd = [f"{scene_xml_path}"]

        world = simulation_data.get("world")
        world_name = "world" if world is None else world["name"]
        rtf_desired = 1 if world_name not in self.worlds else self.worlds[world_name].get("rtf_desired", 1)

        config_dict = simulation_data.get("config", {})
        config_dict["rtf_desired"] = rtf_desired
        config_dict["resources"] = self.resources_paths
        cmd += [f"{config_dict}".replace(" ", "").replace("'", '"')]

        if self.multiverse_clients.get(simulation_name) is not None:
            self.multiverse_clients[simulation_name]["meta_data"] = {
                "world_name": world_name,
                "simulation_name": simulation_name,
            }

            multiverse_dict = {"multiverse_server": self.multiverse_server,
                               "multiverse_client": self.multiverse_clients[simulation_name]}
            multiverse_dict["multiverse_client"]["resources"] = self.resources_paths

            cmd += [f"{multiverse_dict}".replace(" ", "").replace("'", '"')]

        suffix = "_headless" if simulation_data.get("headless", False) else ""
        cmd = [f"{simulation_data['simulator']}{suffix}"] + cmd

        return run_subprocess(cmd)


def main():
    multiverse_launch = MultiverseSimulationLaunch()
    multiverse_launch.run_simulations()


if __name__ == "__main__":
    main()
