import asyncio
import ssl
import sys
from dataclasses import dataclass

from aiohttp import web

from src.application.ports.config_provider import ConfigProviderPort, ConfigStorePort
from src.application.services.direct_remote_service import DirectRemoteService
from src.application.services.gesture_remote_service import GestureRemoteService
from src.infrastructure.audio.browser_voice_capture import (
    BrowserAudioSource,
    BrowserVoiceCapture,
)
from src.infrastructure.camera.browser_debug_display import BrowserDebugDisplay
from src.infrastructure.camera.browser_frame_source import BrowserFrameSource
from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.frame_processor import OpenCvFrameProcessor
from src.infrastructure.hand_tracking.hand_tracking import MediaPipeHandTracker
from src.infrastructure.hand_tracking.model_store import MediaPipeModelStore
from src.infrastructure.network.mac_address import LocalNetworkMacAddressResolver
from src.infrastructure.network.mdns import MdnsPublisher
from src.infrastructure.web.debug_stream import BrowserDebugStream
from src.infrastructure.web.display_metrics import BrowserDisplayMetrics
from src.infrastructure.web.tls import ensure_web_certificate
from src.runtime.builders.config import build_config_provider, build_config_repository
from src.runtime.builders.tv import build_tv_dependencies
from src.shared.config import DEFAULT_CONFIG, AppConfig, load_config_from_env
from src.shared.logging import AppLogger, configure_app_logging
from src.web.app import create_web_app

RESTART_EXIT_CODE = 75


@dataclass(frozen=True)
class WebAppRuntime:
    service: GestureRemoteService
    server: "WebAppServer"
    browser_audio_source: BrowserAudioSource
    restart_control: "RuntimeRestartControl"


class RuntimeRestartControl:
    def __init__(self, service: GestureRemoteService) -> None:
        self._service = service
        self._restart_requested = False

    @property
    def restart_requested(self) -> bool:
        return self._restart_requested

    def request_restart(self) -> None:
        self._restart_requested = True
        self._service.stop()


class WebAppServer:
    def __init__(
        self,
        app: web.Application,
        host: str,
        port: int,
        logger: AppLogger,
        *,
        ssl_context: ssl.SSLContext | None = None,
        mdns_publisher: MdnsPublisher | None = None,
    ) -> None:
        self._app = app
        self._host = host
        self._port = port
        self._logger = logger
        self._ssl_context = ssl_context
        self._mdns_publisher = mdns_publisher
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            self._host,
            self._port,
            ssl_context=self._ssl_context,
        )
        await self._site.start()
        if self._mdns_publisher is not None:
            try:
                await asyncio.to_thread(self._mdns_publisher.start)
            except Exception as error:
                self._logger.error(f"Web UI mDNS advertising failed: {error}")
            self._logger.info(f"Open browser gesture at {self._mdns_publisher.url}")
        scheme = "https" if self._ssl_context is not None else "http"
        self._logger.info(
            f"Web UI listening on {scheme}://{self._host}:{self._port} "
            f"(settings=/settings gesture=/gesture remote=/remote)"
        )

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None
        if self._mdns_publisher is not None:
            try:
                await asyncio.to_thread(self._mdns_publisher.stop)
            except Exception as error:
                self._logger.error(f"Web UI mDNS cleanup failed: {error}")


async def main() -> int:
    runtime = build_web_app_runtime(create_config_provider())
    await runtime.server.start()
    try:
        await runtime.service.run()
    finally:
        await runtime.browser_audio_source.close()
        await runtime.server.stop()
    if runtime.restart_control.restart_requested:
        return RESTART_EXIT_CODE
    return 0


def build_web_app_runtime(
    config_provider: ConfigProviderPort | None = None,
    repository: ConfigStorePort | None = None,
) -> WebAppRuntime:
    if config_provider is None or repository is None:
        repository, provider = create_config_dependencies()
    else:
        provider = config_provider
    config = provider()
    logger = AppLogger()
    tv_deps = build_tv_dependencies(config, logger)
    browser_frame_source = BrowserFrameSource()
    browser_audio_source = BrowserAudioSource()
    debug_stream = BrowserDebugStream()
    display_metrics = BrowserDisplayMetrics()

    MediaPipeModelStore(config).ensure_model()
    service = GestureRemoteService(
        config,
        remote=tv_deps.remote,
        frame_source=browser_frame_source,
        hand_tracker=MediaPipeHandTracker(config),
        camera=CameraZoomController(config),
        frame_processor=OpenCvFrameProcessor(),
        display=BrowserDebugDisplay(debug_stream),
        voice_capture=BrowserVoiceCapture(
            tv_deps.remote,
            browser_audio_source,
            config,
            logger,
        ),
        command_dispatcher=tv_deps.command_dispatcher,
        logger=logger,
        metrics=tv_deps.metrics,
        config_store=repository,
        config_provider=provider,
        mac_address_resolver=LocalNetworkMacAddressResolver(logger),
        display_metrics=display_metrics,
    )
    restart_control = RuntimeRestartControl(service)
    app = create_web_app(
        repository=repository,
        config_provider=provider,
        browser_video_sink=browser_frame_source,
        browser_audio_sink=browser_audio_source,
        debug_source=debug_stream,
        direct_remote=DirectRemoteService(tv_deps.remote, tv_deps.command_dispatcher),
        display_metrics_sink=display_metrics,
        logger=logger,
        runtime_control=restart_control,
    )
    ssl_context = _build_ssl_context(config, logger, auto_generate=True)
    scheme = "https" if ssl_context is not None else "http"
    bind_port = _web_app_port(config, ssl_context)
    mdns_publisher = None
    if config.web.mdns_enabled:
        mdns_publisher = MdnsPublisher(
            config.web.mdns_name,
            bind_port,
            logger,
            path="/gesture",
            scheme=scheme,
            service_label="Web UI",
        )
    return WebAppRuntime(
        service=service,
        server=WebAppServer(
            app,
            config.web.host,
            bind_port,
            logger,
            ssl_context=ssl_context,
            mdns_publisher=mdns_publisher,
        ),
        browser_audio_source=browser_audio_source,
        restart_control=restart_control,
    )


def create_config_dependencies() -> tuple[ConfigStorePort, ConfigProviderPort]:
    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    return repository, build_config_provider(repository)


def create_config_provider() -> ConfigProviderPort:
    _, provider = create_config_dependencies()
    return provider


def _build_ssl_context(
    config: AppConfig,
    logger: AppLogger,
    *,
    auto_generate: bool = False,
) -> ssl.SSLContext | None:
    if not config.web.tls_enabled and not auto_generate:
        return None
    certificate = ensure_web_certificate(
        cert_file=config.web.tls_cert_file,
        key_file=config.web.tls_key_file,
        mdns_name=config.web.mdns_name,
    )
    if certificate.generated:
        logger.info(
            "Generated web TLS certificate: "
            f"cert={certificate.cert_file} key={certificate.key_file} "
            f"hosts={', '.join(certificate.hosts)}"
        )
    logger.info(
        "Using web TLS certificate. Trust this certificate on capture devices "
        f"before opening https://{_mdns_host(config.web.mdns_name)}/gesture"
    )
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(
            certfile=config.web.tls_cert_file,
            keyfile=config.web.tls_key_file,
        )
    except OSError as error:
        logger.error(
            "Could not load web TLS certificate or key: "
            f"cert={config.web.tls_cert_file} key={config.web.tls_key_file} "
            f"error={error}"
        )
        raise
    return context


def _web_app_port(config: AppConfig, ssl_context: ssl.SSLContext | None) -> int:
    if ssl_context is not None and config.web.port == DEFAULT_CONFIG.web.port:
        return 443
    return config.web.port


def _mdns_host(name: str) -> str:
    normalized = name.strip().lower()
    if normalized.endswith(".local"):
        return normalized
    return f"{normalized}.local"


def run(configure_logging: bool = True) -> None:
    if configure_logging:
        configure_app_logging()
    _configure_windows_event_loop_policy()
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        AppLogger().info("Web app stopped.")
        return
    if exit_code:
        raise SystemExit(exit_code)


def _configure_windows_event_loop_policy() -> None:
    if sys.platform != "win32":
        return

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
