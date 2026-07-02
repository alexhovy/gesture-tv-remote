import socket
from typing import Any

from src.shared.logging import AppLogger


class MdnsPublisher:
    def __init__(
        self,
        name: str,
        port: int,
        logger: AppLogger | None = None,
        *,
        path: str = "/",
        scheme: str = "http",
        service_label: str = "Config UI",
    ) -> None:
        self._name = _normalize_name(name)
        self._port = port
        self._path = _normalize_path(path)
        self._scheme = scheme
        self._service_label = service_label
        self._logger = logger or AppLogger()
        self._zeroconf: Any | None = None
        self._service_info: Any | None = None

    @property
    def url(self) -> str:
        url = f"{self._scheme}://{self._name}.local"
        if not (
            self._scheme == "http"
            and self._port == 80
            or self._scheme == "https"
            and self._port == 443
        ):
            url = f"{url}:{self._port}"
        if self._path != "/":
            url = f"{url}{self._path}"
        return url

    @property
    def origin(self) -> str:
        if self._scheme == "http" and self._port == 80:
            return f"http://{self._name}.local"
        if self._scheme == "https" and self._port == 443:
            return f"https://{self._name}.local"
        return f"{self._scheme}://{self._name}.local:{self._port}"

    @property
    def path(self) -> str:
        return self._path

    @property
    def scheme(self) -> str:
        return self._scheme

    @property
    def service_label(self) -> str:
        return self._service_label

    @property
    def name(self) -> str:
        return self._name

    @property
    def port(self) -> int:
        return self._port

    def config_url(self) -> str:
        if self._port == 80:
            return f"http://{self._name}.local"
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
            properties={"path": self._path},
            server=f"{self._name}.local.",
        )
        self._zeroconf.register_service(self._service_info)
        self._logger.info(f"{self._service_label} advertised at {self.url}")

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


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path if path.startswith("/") else f"/{path}"
    return normalized.rstrip("/") or "/"


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
        if isinstance(host, str) and not host.startswith("127."):
            return host
    return "127.0.0.1"
