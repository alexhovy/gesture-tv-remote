import socket
from dataclasses import dataclass

from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig


@dataclass(frozen=True)
class WakeOnLanResult:
    attempted: bool
    sent_packets: int
    reason: str | None = None


class WakeOnLanSender:
    def __init__(self, config: AppConfig, logger: LoggerPort) -> None:
        self._config = config
        self._logger = logger

    def wake(self) -> WakeOnLanResult:
        tv_config = self._config.tv
        if not tv_config.wake_enabled:
            return WakeOnLanResult(attempted=False, sent_packets=0, reason="disabled")
        if not tv_config.mac_address.strip():
            return WakeOnLanResult(
                attempted=False,
                sent_packets=0,
                reason="missing_mac_address",
            )

        packet = _magic_packet(tv_config.mac_address)
        address = (tv_config.wake_broadcast_address, tv_config.wake_port)
        sent_packets = 0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for _ in range(tv_config.wake_packet_count):
                sock.sendto(packet, address)
                sent_packets += 1

        self._logger.info(
            "Sent Wake-on-LAN magic packet "
            f"count={sent_packets} "
            f"broadcast={tv_config.wake_broadcast_address}:{tv_config.wake_port}"
        )
        return WakeOnLanResult(attempted=True, sent_packets=sent_packets)


def _magic_packet(mac_address: str) -> bytes:
    normalized = mac_address.strip().replace("-", "").replace(":", "")
    mac_bytes = bytes.fromhex(normalized)
    if len(mac_bytes) != 6:
        raise ValueError("tv_mac_address must be a MAC address")
    return b"\xff" * 6 + mac_bytes * 16
