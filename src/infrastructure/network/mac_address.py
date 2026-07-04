import re
import socket
import subprocess

from src.shared.logging import AppLogger

_MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")


class LocalNetworkMacAddressResolver:
    def __init__(self, logger: AppLogger) -> None:
        self._logger = logger

    def resolve(self, host: str) -> str | None:
        try:
            ip_address = socket.gethostbyname(host)
        except OSError as error:
            self._logger.debug(f"Could not resolve TV host {host}: {error}")
            return None

        for command in _commands_for(ip_address):
            output = _run_command(command)
            if output is None:
                continue
            mac_address = _extract_mac_address(output)
            if mac_address is not None:
                return mac_address

        return None


def _commands_for(ip_address: str) -> tuple[tuple[str, ...], ...]:
    return (
        ("ip", "neigh", "show", ip_address),
        ("ip", "neigh", "get", ip_address),
        ("arp", "-n", ip_address),
        ("arp", "-a", ip_address),
    )


def _run_command(command: tuple[str, ...]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _extract_mac_address(output: str) -> str | None:
    match = _MAC_PATTERN.search(output)
    if match is None:
        return None
    return match.group(0).lower().replace("-", ":")
