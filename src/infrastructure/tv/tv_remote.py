from src.application.ports.tv_remote import CapabilityStatus, TvAdapterCapabilities


TV_ADAPTER_ANDROIDTV = "androidtv"
TV_ADAPTER_SAMSUNG = "samsung"
TV_ADAPTER_WEBOS = "webos"
TV_ADAPTER_ROKU = "roku"

SUPPORTED_TV_ADAPTERS = {
    TV_ADAPTER_ANDROIDTV,
    TV_ADAPTER_SAMSUNG,
    TV_ADAPTER_WEBOS,
    TV_ADAPTER_ROKU,
}


class TvRemoteCommandError(ValueError):
    pass
