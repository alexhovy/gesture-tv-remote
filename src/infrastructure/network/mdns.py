import socket

from src.shared.logging import AppLogger


class MdnsPublisher:
    def __init__(
        self,
        name: str,
        port: int,
        logger: AppLogger | None = None,
    ) -> None:
        self._name = _normalize_name(name)
        self._port = port
        self._logger = logger or AppLogger()
        self._zeroconf = None
        self._service_info = None

    @property
    def url(self) -> str:
        return f"http://{self._name}.local:{self._port}"

    def start(self) -> None:
        from zeroconf import ServiceInfo, Zeroconf

        address = _local_ipv4_address()
        self._zeroconf = Zeroconf()
        self._service_info = ServiceInfo(
            "_http._tcp.local.",
            f"{self._name}._http._tcp.local.",
            addresses=[socket.inet_aton(address)],
            port=self._port,
            properties={"path": "/"},
            server=f"{self._name}.local.",
        )
        self._zeroconf.register_service(self._service_info)
        self._logger.info(f"Config UI advertised at {self.url}")

    def stop(self) -> None:
        if self._zeroconf is None:
            return
        if self._service_info is not None:
            self._zeroconf.unregister_service(self._service_info)
        self._zeroconf.close()
        self._zeroconf = None
        self._service_info = None


def _normalize_name(name: str) -> str:
    normalized = name.strip().lower()
    if normalized.endswith(".local"):
        normalized = normalized[: -len(".local")]
    normalized = "".join(
        character for character in normalized if _is_mdns_name_char(character)
    )
    if not normalized:
        raise ValueError(
            "mDNS name must contain at least one letter, number, or hyphen"
        )
    return normalized


def _is_mdns_name_char(character: str) -> bool:
    return character.isalnum() or character == "-"


def _local_ipv4_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
            if address:
                return address
    except OSError:
        pass

    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return "127.0.0.1"

    for address in addresses:
        host = address[4][0]
        if not host.startswith("127."):
            return host
    return "127.0.0.1"
