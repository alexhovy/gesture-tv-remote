from src.infrastructure.androidtv_remote import AndroidTvRemoteClient
from src.infrastructure.roku_remote import RokuRemoteClient
from src.infrastructure.samsung_remote import SamsungTvRemoteClient
from src.infrastructure.tv_remote import (
    TV_ADAPTER_ANDROIDTV,
    TV_ADAPTER_ROKU,
    TV_ADAPTER_SAMSUNG,
    TV_ADAPTER_WEBOS,
    SUPPORTED_TV_ADAPTERS,
    TvRemoteClient,
)
from src.infrastructure.webos_remote import WebOsRemoteClient
from src.shared.config import AppConfig


def create_tv_remote_client(config: AppConfig) -> TvRemoteClient:
    adapter = config.tv_adapter.lower()
    if adapter == TV_ADAPTER_ANDROIDTV:
        return AndroidTvRemoteClient(config)
    if adapter == TV_ADAPTER_SAMSUNG:
        return SamsungTvRemoteClient(config)
    if adapter == TV_ADAPTER_WEBOS:
        return WebOsRemoteClient(config)
    if adapter == TV_ADAPTER_ROKU:
        return RokuRemoteClient(config)

    supported = ", ".join(sorted(SUPPORTED_TV_ADAPTERS))
    raise ValueError(f"Unsupported TV adapter {config.tv_adapter!r}. Use one of: {supported}")
