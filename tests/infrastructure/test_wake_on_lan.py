import socket
import unittest
from unittest.mock import patch

from src.infrastructure.tv.wake_on_lan import WakeOnLanSender, _magic_packet
from tests.helpers.config_helpers import app_config


class WakeOnLanTests(unittest.TestCase):
    def test_magic_packet_repeats_mac_address(self) -> None:
        packet = _magic_packet("00:11:22:33:44:55")

        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:], bytes.fromhex("001122334455") * 16)

    def test_sender_sends_configured_packet_count_to_broadcast_address(self) -> None:
        fake_socket = FakeSocket()
        config = app_config(
            tv_wake_enabled=True,
            tv_mac_address="00:11:22:33:44:55",
            tv_wake_broadcast_address="10.0.0.255",
            tv_wake_port=7,
            tv_wake_packet_count=2,
        )

        with patch("src.infrastructure.tv.wake_on_lan.socket.socket") as socket_class:
            socket_class.return_value = fake_socket
            result = WakeOnLanSender(config, FakeLogger()).wake()

        self.assertTrue(result.attempted)
        self.assertEqual(result.sent_packets, 2)
        self.assertEqual(
            fake_socket.options,
            [(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)],
        )
        self.assertEqual(
            [address for _, address in fake_socket.sent],
            [("10.0.0.255", 7), ("10.0.0.255", 7)],
        )


class FakeSocket:
    def __init__(self) -> None:
        self.options: list[tuple[int, int, int]] = []
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def setsockopt(self, level, option, value) -> None:
        self.options.append((level, option, value))

    def sendto(self, packet, address) -> None:
        self.sent.append((packet, address))


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)

    def debug(self, message: str) -> None:
        self.messages.append(message)


if __name__ == "__main__":
    unittest.main()
