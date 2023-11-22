#!/usr/bin/env python3

import dataclasses
from typing import List, Dict, TypeVar

from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

from multiverse_client_pybind import MultiverseClientPybind  # noqa

T = TypeVar("T")


@dataclasses.dataclass
class MultiverseMetaData:
    world_name: str = "world"
    simulation_name: str = "ros"
    length_unit: str = "m"
    angle_unit: str = "rad"
    mass_unit: str = "kg"
    time_unit: str = "s"
    handedness: str = "rhs"


@dataclasses.dataclass
class SocketAddress:
    host: str = "tcp://127.0.0.1"
    port: str = ""


class MultiverseNode(Node):
    _executor: MultiThreadedExecutor
    _server_addr: SocketAddress = SocketAddress(host="tcp://127.0.0.1", port="7000")
    _client_addr: SocketAddress
    _meta_data: MultiverseMetaData
    _multiverse_socket: MultiverseClientPybind

    def __init__(
        self,
        node_name: str,
        client_addr: SocketAddress,
        multiverse_meta_data: MultiverseMetaData = MultiverseMetaData(),
    ) -> None:
        if not isinstance(client_addr.port, str) or client_addr.port == "":
            raise ValueError(f"Must specify client port for {self.__class__.__name__}")
        super().__init__(node_name=f"{node_name}{client_addr.port}")
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self)
        self._send_data = None
        self._client_addr = client_addr
        self._meta_data = multiverse_meta_data
        self._multiverse_socket = MultiverseClientPybind(
            f"{self._server_addr.host}:{self._server_addr.port}"
        )
        self.request_meta_data = {
            "meta_data": self._meta_data.__dict__,
            "send": {},
            "receive": {},
        }

    def run(self) -> None:
        self.get_logger().info(f"[Client {self._client_addr.port}] Start {self.__class__.__name__}")
        self._run()

    def _run(self) -> None:
        raise NotImplementedError(
            f"Must implement _run() for {self.__class__.__name__}"
        )

    @property
    def request_meta_data(self) -> Dict:
        return self._request_meta_data

    @request_meta_data.setter
    def request_meta_data(self, request_meta_data: Dict) -> None:
        self._request_meta_data = request_meta_data
        self._multiverse_socket.set_request_meta_data(self._request_meta_data)

    @property
    def response_meta_data(self) -> Dict:
        response_meta_data = self._multiverse_socket.get_response_meta_data()
        if not response_meta_data:
            print(
                f"[Client {self._client_addr.port}] Receive empty response meta data."
            )
        return response_meta_data

    @property
    def send_data(self) -> List[float]:
        return self._send_data

    @send_data.setter
    def send_data(self, send_data: List[float]) -> None:
        self._send_data = send_data
        self._multiverse_socket.set_send_data(self._send_data)

    @property
    def receive_data(self) -> List[float]:
        receive_data = self._multiverse_socket.get_receive_data()
        if not receive_data:
            self.get_logger().warn(f"[Client {self._client_addr.port}] Receive empty data.")
        return receive_data

    def _bind_request_meta_data(self, request_meta_data: T) -> T:
        pass

    def _bind_response_meta_data(self, response_meta_data: T) -> T:
        pass

    def _bind_send_data(self, send_data: T) -> T:
        pass

    def _bind_receive_data(self, receive_data: T) -> T:
        pass

    def _connect(self) -> None:
        self._multiverse_socket.connect(self._client_addr.host, self._client_addr.port)
        self._multiverse_socket.start()

    def _disconnect(self) -> None:
        self._multiverse_socket.disconnect()

    def _communicate(self, resend_request_meta_data: bool = False) -> None:
        self._multiverse_socket.communicate(resend_request_meta_data)

    def _restart(self) -> None:
        self._disconnect()
        self._connect()
