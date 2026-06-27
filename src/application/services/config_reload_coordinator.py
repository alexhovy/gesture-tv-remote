import asyncio
from typing import Protocol

from src.application.ports.config_provider import ConfigProviderPort
from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig, apply_reloadable_config

CONFIG_RELOAD_INTERVAL_SECONDS = 1.0


class ReloadableConfigTarget(Protocol):
    def update_config(self, config: AppConfig) -> None: ...


class ConfigReloadCoordinator:
    def __init__(
        self,
        config: AppConfig,
        *,
        gesture_session: ReloadableConfigTarget,
        voice_capture: ReloadableConfigTarget,
        camera: ReloadableConfigTarget,
        hand_tracker: ReloadableConfigTarget,
        logger: LoggerPort,
        config_provider: ConfigProviderPort | None = None,
    ) -> None:
        self._config = config
        self._gesture_session = gesture_session
        self._voice_capture = voice_capture
        self._camera = camera
        self._hand_tracker = hand_tracker
        self._logger = logger
        self._config_provider = config_provider
        self._last_reload_time = 0.0

    @property
    def config(self) -> AppConfig:
        return self._config

    async def reload_if_needed(self, now: float) -> AppConfig:
        if not self._should_reload(now):
            return self._config

        try:
            assert self._config_provider is not None
            latest_config = await asyncio.to_thread(self._config_provider)
            config = apply_reloadable_config(self._config, latest_config)
        except ValueError as error:
            self._logger.error(f"Config reload skipped: {error}")
            return self._config

        self._apply(config)
        return self._config

    def reload_if_needed_sync(self, now: float) -> AppConfig:
        if not self._should_reload(now):
            return self._config

        try:
            assert self._config_provider is not None
            latest_config = self._config_provider()
            config = apply_reloadable_config(self._config, latest_config)
        except ValueError as error:
            self._logger.error(f"Config reload skipped: {error}")
            return self._config

        self._apply(config)
        return self._config

    def _should_reload(self, now: float) -> bool:
        if self._config_provider is None:
            return False
        if now - self._last_reload_time < CONFIG_RELOAD_INTERVAL_SECONDS:
            return False
        self._last_reload_time = now
        return True

    def _apply(self, config: AppConfig) -> None:
        if config == self._config:
            return

        self._config = config
        self._gesture_session.update_config(config)
        self._voice_capture.update_config(config)
        self._camera.update_config(config)
        self._hand_tracker.update_config(config)
        self._logger.info("Reloaded live config settings.")
