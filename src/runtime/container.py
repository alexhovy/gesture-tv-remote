from __future__ import annotations

from src.application.ports.config_provider import ConfigProviderPort, ConfigStorePort
from src.application.services.gesture_remote_service import GestureRemoteService
from src.infrastructure.network.mac_address import LocalNetworkMacAddressResolver
from src.runtime.builders.audio import build_voice_capture
from src.runtime.builders.camera import build_camera_dependencies
from src.runtime.builders.config import build_config_provider, build_config_repository
from src.runtime.builders.tv import build_tv_dependencies
from src.shared.config import load_config_from_env
from src.shared.logging import AppLogger


def build_gesture_remote_service(
    config_provider: ConfigProviderPort | None = None,
    config_store: ConfigStorePort | None = None,
) -> GestureRemoteService:
    repository: ConfigStorePort | None
    if config_provider is None:
        repository = build_config_repository(load_config_from_env())
        provider = build_config_provider(repository)
    else:
        repository = config_store
        provider = config_provider
    config = provider()
    logger = AppLogger()

    tv_deps = build_tv_dependencies(config, logger)
    camera_deps = build_camera_dependencies(config)
    voice_capture = build_voice_capture(tv_deps.remote, config, logger)
    return GestureRemoteService(
        config,
        remote=tv_deps.remote,
        frame_source=camera_deps.frame_source,
        hand_tracker=camera_deps.hand_tracker,
        camera=camera_deps.camera,
        frame_processor=camera_deps.frame_processor,
        display=camera_deps.display,
        voice_capture=voice_capture,
        command_dispatcher=tv_deps.command_dispatcher,
        logger=logger,
        metrics=tv_deps.metrics,
        config_store=repository,
        config_provider=provider,
        mac_address_resolver=LocalNetworkMacAddressResolver(logger),
    )
