from typing import Protocol

from src.shared.config import AppConfig


class ConfigProviderPort(Protocol):
    def __call__(self) -> AppConfig: ...


class ConfigStorePort(Protocol):
    def get_config(self) -> AppConfig | None: ...

    def save_config(self, config: AppConfig) -> None: ...

    def reset_config(self) -> None: ...
