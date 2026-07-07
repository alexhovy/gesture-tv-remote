import asyncio
import time

from src.application.ports.camera import CameraPort, FrameProcessorPort
from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.config_provider import ConfigProviderPort, ConfigStorePort
from src.application.ports.display import DisplayPort
from src.application.ports.display_metrics import DisplayMetricsPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.ports.hand_tracker import HandTrackerPort
from src.application.ports.logger import LoggerPort
from src.application.ports.mac_address_resolver import MacAddressResolverPort
from src.application.ports.tv_remote import AppVoiceInputRequest, TVRemotePort
from src.application.ports.voice_capture import VoiceCapturePort
from src.application.services.coordinators.cleanup import CleanupCoordinator
from src.application.services.coordinators.config_reload import ConfigReloadCoordinator
from src.application.services.coordinators.display_debug import DisplayDebugCoordinator
from src.application.services.coordinators.runtime_loop import RuntimeLoopCoordinator
from src.application.services.pipeline_metrics import PipelineMetrics
from src.domain.session import GestureSession
from src.shared.config import AppConfig, replace_config_value


class GestureRemoteService:
    def __init__(
        self,
        config: AppConfig,
        *,
        remote: TVRemotePort,
        frame_source: FrameSourcePort,
        hand_tracker: HandTrackerPort,
        camera: CameraPort,
        frame_processor: FrameProcessorPort,
        display: DisplayPort,
        voice_capture: VoiceCapturePort,
        command_dispatcher: CommandDispatcherPort,
        logger: LoggerPort,
        metrics: PipelineMetrics,
        config_store: ConfigStorePort | None = None,
        config_provider: ConfigProviderPort | None = None,
        mac_address_resolver: MacAddressResolverPort | None = None,
        display_metrics: DisplayMetricsPort | None = None,
        gesture_session: GestureSession | None = None,
    ) -> None:
        self._config = config
        self._remote = remote
        self._frame_source = frame_source
        self._voice_capture = voice_capture
        self._logger = logger
        self._config_store = config_store
        self._mac_address_resolver = mac_address_resolver
        self._gesture_session = gesture_session or GestureSession(config)
        self._voice_task: asyncio.Task | None = None
        config_reload = ConfigReloadCoordinator(
            config,
            gesture_session=self._gesture_session,
            voice_capture=voice_capture,
            camera=camera,
            hand_tracker=hand_tracker,
            logger=logger,
            config_provider=config_provider,
        )
        display_debug = DisplayDebugCoordinator(display, logger)
        self._runtime_loop = RuntimeLoopCoordinator(
            frame_source=frame_source,
            hand_tracker=hand_tracker,
            camera=camera,
            frame_processor=frame_processor,
            voice_capture=voice_capture,
            command_dispatcher=command_dispatcher,
            gesture_session=self._gesture_session,
            metrics=metrics,
            logger=logger,
            config_reload=config_reload,
            display_debug=display_debug,
            display_metrics=display_metrics,
        )
        self._cleanup = CleanupCoordinator(
            remote=remote,
            frame_source=frame_source,
            hand_tracker=hand_tracker,
            display=display,
            command_dispatcher=command_dispatcher,
            logger=logger,
        )

    async def run(self) -> None:
        if await self._connect_remote():
            await self._store_discovered_wake_settings()
        else:
            self._logger.info(
                "TV connection failed. Continuing without an initial TV connection."
            )

        if not await asyncio.to_thread(self._frame_source.is_open):
            self._logger.error("Could not open webcam.")
            await self._cleanup.cleanup(None)
            return

        self._remote.set_app_voice_input_handler(self._handle_app_voice_input)
        try:
            self._voice_task = await self._runtime_loop.run(self._voice_task)
        finally:
            await self._cleanup.cleanup(self._voice_task)

    async def _handle_app_voice_input(self, request: AppVoiceInputRequest) -> None:
        context = (
            f"android_app_voice session_id={request.session_id} "
            f"package={request.package_name or 'unknown'}"
        )
        if self._voice_task is not None and not self._voice_task.done():
            self._logger.info(
                "Rejecting Android app voice input because microphone capture "
                f"is already running: {context}"
            )
            request.stream.end()
            return

        self._logger.info(f"Starting Android app voice input capture: {context}")
        self._voice_task = asyncio.create_task(
            self._voice_capture.capture_stream(request.stream, context)
        )

    def stop(self) -> None:
        self._runtime_loop.stop()

    async def _connect_remote(self) -> bool:
        if not self._config.tv.wake_enabled:
            return await self._remote.connect()

        await self._remote.wake()
        deadline = time.monotonic() + self._config.tv.wake_connect_timeout_seconds
        while True:
            if await self._remote.connect():
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(
                min(
                    self._config.tv.wake_connect_retry_seconds,
                    max(0.0, deadline - time.monotonic()),
                )
            )

    async def _store_discovered_wake_settings(self) -> None:
        if self._config_store is None or self._mac_address_resolver is None:
            return

        mac_address = await self._remote.discover_mac_address()
        if mac_address is None:
            mac_address = self._mac_address_resolver.resolve(self._config.tv.host)
        broadcast_address = self._mac_address_resolver.resolve_broadcast_address(
            self._config.tv.host
        )
        if mac_address is None and broadcast_address is None:
            self._logger.info(
                "Could not discover TV wake settings. Wake-on-LAN may need manual "
                "network configuration."
            )
            return

        saved_config = self._config_store.get_config() or self._config
        updated_config = saved_config
        message_parts: list[str] = []
        if mac_address is not None:
            if saved_config.tv.mac_address.lower() != mac_address.lower():
                updated_config = replace_config_value(
                    updated_config,
                    "tv_mac_address",
                    mac_address,
                )
                message_parts.append("TV MAC address")
            if not saved_config.tv.wake_enabled:
                updated_config = replace_config_value(
                    updated_config,
                    "tv_wake_enabled",
                    True,
                )
                message_parts.append("Wake-on-LAN enabled")
        if (
            broadcast_address is not None
            and saved_config.tv.wake_broadcast_address != broadcast_address
        ):
            updated_config = replace_config_value(
                updated_config,
                "tv_wake_broadcast_address",
                broadcast_address,
            )
            message_parts.append("wake broadcast address")

        if updated_config == saved_config:
            return

        self._config_store.save_config(updated_config)
        self._config = updated_config
        self._logger.info(
            "Updated discovered TV wake settings: " + ", ".join(message_parts) + "."
        )
