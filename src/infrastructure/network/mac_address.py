import re
import socket
import subprocess
from ipaddress import IPv4Address, ip_address

from src.application.ports.logger import LoggerPort

_MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")


class LocalNetworkMacAddressResolver:
    def __init__(self, logger: LoggerPort) -> None:
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

    def resolve_broadcast_address(self, host: str) -> str | None:
        try:
            tv_ip_address = ip_address(socket.gethostbyname(host))
        except OSError as error:
            self._logger.debug(f"Could not resolve TV host {host}: {error}")
            return None
        except ValueError:
            return None
        if not isinstance(tv_ip_address, IPv4Address):
            return None

        local_ip_address = _local_ipv4_for(str(tv_ip_address))
        if local_ip_address is None:
            return None
        try:
            local_ip = ip_address(local_ip_address)
        except ValueError:
            return None
        if not isinstance(local_ip, IPv4Address):
            return None

        tv_octets = str(tv_ip_address).split(".")
        local_octets = str(local_ip).split(".")
        if tv_octets[:3] != local_octets[:3]:
            self._logger.debug(
                "TV host is not on the selected local /24 network. "
                f"host={tv_ip_address} local={local_ip}"
            )
            return None
        return ".".join((*tv_octets[:3], "255"))


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


def _local_ipv4_for(destination: str) -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((destination, 9))
        host = probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()
    return host


def _extract_mac_address(output: str) -> str | None:
    match = _MAC_PATTERN.search(output)
    if match is None:
        return None
    return match.group(0).lower().replace("-", ":")
