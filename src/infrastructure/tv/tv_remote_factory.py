from src.application.ports.tv_remote import TVRemotePort
from src.infrastructure.tv.androidtv_remote import AndroidTvRemoteClient
from src.infrastructure.tv.appletv_remote import AppleTvRemoteClient
from src.infrastructure.tv.roku_remote import RokuRemoteClient
from src.infrastructure.tv.samsung_remote import SamsungTvRemoteClient
from src.infrastructure.tv.tv_remote import (
    SUPPORTED_TV_ADAPTERS,
    TV_ADAPTER_ANDROIDTV,
    TV_ADAPTER_APPLETV,
    TV_ADAPTER_ROKU,
    TV_ADAPTER_SAMSUNG,
    TV_ADAPTER_WEBOS,
)
from src.infrastructure.tv.webos_remote import WebOsRemoteClient
from src.shared.config import AppConfig


def create_tv_remote_client(config: AppConfig) -> TVRemotePort:
    adapter = config.tv.adapter.lower()
    if adapter == TV_ADAPTER_APPLETV:
        return AppleTvRemoteClient(config)
    if adapter == TV_ADAPTER_ANDROIDTV:
        return AndroidTvRemoteClient(config)
    if adapter == TV_ADAPTER_SAMSUNG:
        return SamsungTvRemoteClient(config)
    if adapter == TV_ADAPTER_WEBOS:
        return WebOsRemoteClient(config)
    if adapter == TV_ADAPTER_ROKU:
        return RokuRemoteClient(config)

    supported = ", ".join(sorted(SUPPORTED_TV_ADAPTERS))
    raise ValueError(
        f"Unsupported TV adapter {config.tv.adapter!r}. Use one of: {supported}"
    )
