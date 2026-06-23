from __future__ import annotations

from src.application.ports.config_provider import ConfigStorePort
from src.application.services.gesture_remote_service import GestureRemoteService
from src.runtime.config_server import ConfigServerRunner
from src.shared.config import AppConfig, load_config_from_env
from src.shared.logging import AppLogger


def build_config_repository(config: AppConfig):
    from src.infrastructure.data_access.sqlite_store import SqliteStore
    from src.infrastructure.repositories.config_repository import ConfigRepository

    return ConfigRepository(SqliteStore(config.config_db_file))


def build_config_provider(repository: ConfigStorePort):
    bootstrap_config = load_config_from_env()

    def provide_config() -> AppConfig:
        saved_config = repository.get_config()
        return load_config_from_env(base_config=saved_config or bootstrap_config)

    return provide_config


def build_runtime_config() -> AppConfig:
    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    saved_config = repository.get_config()
    return load_config_from_env(base_config=saved_config or bootstrap_config)


def build_gesture_remote_service(config_provider=None) -> GestureRemoteService:
    import cv2

    from src.application.services.pipeline_metrics import PipelineMetrics
    from src.application.services.remote_command_dispatcher import RemoteCommandDispatcher
    from src.infrastructure.audio.voice_capture import MicrophoneVoiceCapture
    from src.infrastructure.camera.camera_zoom import CameraZoomController
    from src.infrastructure.camera.display import OpenCvDisplay
    from src.infrastructure.camera.frame_processor import OpenCvFrameProcessor
    from src.infrastructure.camera.frame_source import LatestFrameSource
    from src.infrastructure.hand_tracking.hand_tracking import MediaPipeHandTracker
    from src.infrastructure.hand_tracking.model_store import MediaPipeModelStore
    from src.infrastructure.tv.tv_remote_factory import create_tv_remote_client

    provider = config_provider or build_config_provider(
        build_config_repository(load_config_from_env())
    )
    config = provider()
    logger = AppLogger()
    model_store = MediaPipeModelStore(config)
    model_store.ensure_model()
    remote = create_tv_remote_client(config)
    frame_source = LatestFrameSource(cv2.VideoCapture(config.camera.webcam_index))
    hand_tracker = MediaPipeHandTracker(config)
    camera = CameraZoomController(config)
    frame_processor = OpenCvFrameProcessor()
    display = OpenCvDisplay()
    voice_capture = MicrophoneVoiceCapture(remote, config, logger)
    command_dispatcher = RemoteCommandDispatcher(remote, logger)
    metrics = PipelineMetrics(config.tv.adapter)
    return GestureRemoteService(
        config,
        remote=remote,
        frame_source=frame_source,
        hand_tracker=hand_tracker,
        camera=camera,
        frame_processor=frame_processor,
        display=display,
        voice_capture=voice_capture,
        command_dispatcher=command_dispatcher,
        logger=logger,
        metrics=metrics,
        config_provider=provider,
    )


def build_config_server_runner(
    host: str | None = None,
    port: int | None = None,
) -> ConfigServerRunner:
    from src.infrastructure.network.mdns import MdnsPublisher
    from src.web.config_app import create_config_server

    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    config_provider = build_config_provider(repository)
    config = config_provider()
    bind_host = config.web.host if host is None else host
    bind_port = config.web.port if port is None else port
    server = create_config_server(
        repository,
        config_provider,
        bind_host,
        bind_port,
    )
    logger = AppLogger()
    mdns_publisher = None
    if config.web.mdns_enabled:
        mdns_publisher = MdnsPublisher(config.web.mdns_name, bind_port, logger)
    return ConfigServerRunner(server, mdns_publisher, logger)
