import asyncio
from dataclasses import dataclass
from types import MethodType
from typing import Any

from src.application.ports.tv_remote import (
    CapabilityStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)
from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import TV_ADAPTER_ANDROIDTV
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class AndroidTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = None
        self._logger = AppLogger()

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            power=CapabilityStatus.NOT_IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.NOT_IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.IMPLEMENTED,
                native_voice_search=CapabilityStatus.IMPLEMENTED,
                app_voice_input=CapabilityStatus.IMPLEMENTED,
                app_text_input=CapabilityStatus.NOT_IMPLEMENTED,
                notes=(
                    "Remote microphone streaming uses Android TV Remote Protocol "
                    "voice sessions.",
                    "Foreground app voice input attaches to an app-requested "
                    "voice session without sending global search.",
                ),
            ),
            connection_type="androidtvremote2 TLS remote protocol",
            known_limitations=(
                "Only key commands and Android TV Remote Protocol microphone "
                "streaming are implemented.",
                "Power, text input, source selection, and media controls are "
                "not mapped.",
            ),
        )

    async def connect(self) -> bool:
        from androidtvremote2 import (
            AndroidTVRemote,
            CannotConnect,
            ConnectionClosed,
            InvalidAuth,
        )

        self._config.tv.android_cert_file.parent.mkdir(parents=True, exist_ok=True)
        remote = AndroidTVRemote(
            self._config.app_name,
            str(self._config.tv.android_cert_file),
            str(self._config.tv.android_key_file),
            self._config.tv.host,
            enable_voice=True,
        )

        if await remote.async_generate_cert_if_missing():
            self._logger.info(
                "Generated "
                f"{self._config.tv.android_cert_file} and "
                f"{self._config.tv.android_key_file}"
            )

        try:
            await remote.async_connect()
        except InvalidAuth:
            self._logger.info("Android TV needs pairing before commands can be sent.")
            self._logger.info("Starting pairing. Enter the code shown on your TV.")
            try:
                await remote.async_start_pairing()
                pairing_code = await asyncio.to_thread(input, "Pairing code: ")
                pairing_code = pairing_code.strip()
                await remote.async_finish_pairing(pairing_code)
                await remote.async_connect()
            except (CannotConnect, ConnectionClosed, InvalidAuth) as error:
                self._logger.error(f"Android TV pairing failed: {error}")
                return False
        except (CannotConnect, ConnectionClosed) as error:
            self._logger.error(
                f"Could not connect to Android TV at {self._config.tv.host}: {error}"
            )
            return False

        self._remote = remote
        _AndroidAppVoiceSessionBroker.for_remote(remote, self._logger)
        self._logger.info(f"Connected to Android TV at {self._config.tv.host}")
        return True

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        from androidtvremote2 import ConnectionClosed

        adapter_command = translate_tv_command(TV_ADAPTER_ANDROIDTV, command)
        try:
            await call_remote_method(
                self._remote.send_key_command,
                adapter_command,
                offload_sync=False,
            )
        except ConnectionClosed:
            self._logger.error("Android TV connection closed. Command not sent.")
        except ValueError as error:
            self._logger.error(f"Invalid Android TV command {adapter_command}: {error}")

    async def start_voice(self, mode: VoiceInputMode):
        if self._remote is None:
            return None
        if mode == VoiceInputMode.AUTO:
            broker = _AndroidAppVoiceSessionBroker.for_remote(
                self._remote,
                self._logger,
            )
            has_pending_app_session = broker.has_pending_session()
            self._logger.info(
                "Android app voice pending: "
                f"{'yes' if has_pending_app_session else 'no'}"
            )
            if has_pending_app_session:
                self._logger.info("Android voice route: app_pending")
                return await broker.start_voice()
            self._logger.info("Android voice route: global_search")
            return await self._remote.start_voice()
        if mode == VoiceInputMode.REMOTE_MIC_STREAM:
            return await self._remote.start_voice()
        if mode == VoiceInputMode.NATIVE_VOICE_SEARCH:
            await call_remote_method(
                self._remote.send_key_command,
                "SEARCH",
                offload_sync=False,
            )
            return None
        self._logger.info(
            f"Android TV voice input mode is not implemented: {mode.value}"
        )
        return None

    async def disconnect(self) -> None:
        if self._remote is not None:
            await call_remote_method(self._remote.disconnect, offload_sync=False)


@dataclass(frozen=True)
class _AppVoiceSession:
    session_id: int
    package_name: str


class _ProtocolVoiceStream:
    def __init__(self, protocol: Any, session: _AppVoiceSession) -> None:
        self._protocol = protocol
        self.session = session
        self._closed = False

    def send_chunk(self, chunk: bytes) -> bool:
        if self._closed:
            return False
        self._protocol.send_voice_chunk(chunk, self.session.session_id)
        return True

    def end(self) -> None:
        if not self._closed:
            self._protocol.end_voice(self.session.session_id)
            self._closed = True


class _AndroidAppVoiceSessionBroker:
    _REMOTE_ATTRIBUTE = "_gesture_tv_app_voice_broker"

    def __init__(self, remote: Any, logger: AppLogger) -> None:
        self._remote = remote
        self._logger = logger
        self._protocol = self._get_protocol(remote)
        self._loop = self._protocol._loop
        self._pending_session: _AppVoiceSession | None = None
        self._waiting_session: asyncio.Future[_AppVoiceSession] | None = None
        self._original_handle_message = self._protocol._handle_message
        self._protocol._handle_message = MethodType(
            _AndroidAppVoiceSessionBroker._handle_message,
            self,
        )

    @classmethod
    def for_remote(
        cls,
        remote: Any,
        logger: AppLogger,
    ) -> "_AndroidAppVoiceSessionBroker | _NativeAppVoiceSessionBroker":
        protocol = cls._get_protocol(remote)
        if getattr(protocol, "start_app_voice", None) is not None:
            return _NativeAppVoiceSessionBroker(protocol)

        broker = getattr(remote, cls._REMOTE_ATTRIBUTE, None)
        if broker is None:
            broker = cls(remote, logger)
            setattr(remote, cls._REMOTE_ATTRIBUTE, broker)
        return broker

    async def start_voice(self, timeout: float = 2.0) -> _ProtocolVoiceStream:
        start_app_voice = getattr(self._protocol, "start_app_voice", None)
        if start_app_voice is not None:
            return await start_app_voice(timeout)

        if self._protocol.transport is None or self._protocol.transport.is_closing():
            from androidtvremote2 import ConnectionClosed

            raise ConnectionClosed("Connection has been lost")

        if self._protocol._voice_lock.locked():
            raise TimeoutError("Voice session already in progress")

        await self._protocol._voice_lock.acquire()
        try:
            session = self._pending_session
            self._pending_session = None
            if session is None:
                self._waiting_session = self._loop.create_future()
                self._logger.info("Waiting for Android app voice input request.")
                session = await self._protocol._async_wait_for_future_or_con_lost(
                    self._waiting_session,
                    timeout,
                )

            self._logger.info(
                "Android app voice input session started: "
                f"session_id={session.session_id} "
                f"package={session.package_name or 'unknown'}"
            )
            return _ProtocolVoiceStream(self._protocol, session)
        finally:
            self._waiting_session = None
            self._protocol._voice_lock.release()

    def has_pending_session(self) -> bool:
        return self._pending_session is not None

    def _handle_message(self, raw_msg: bytes) -> None:
        app_voice_session = self._parse_app_voice_begin(raw_msg)
        if app_voice_session is not None:
            self._record_app_voice_begin(app_voice_session)
        self._original_handle_message(raw_msg)

    def _parse_app_voice_begin(self, raw_msg: bytes) -> _AppVoiceSession | None:
        on_voice_begin = getattr(self._protocol, "_on_voice_begin", None)
        if on_voice_begin is not None and not on_voice_begin.done():
            return None

        from google.protobuf.message import DecodeError
        from androidtvremote2.remotemessage_pb2 import RemoteMessage

        msg = RemoteMessage()
        try:
            msg.ParseFromString(raw_msg)
        except DecodeError:
            return None
        if not msg.HasField("remote_voice_begin"):
            return None
        return _AppVoiceSession(
            session_id=int(msg.remote_voice_begin.session_id),
            package_name=msg.remote_voice_begin.package_name,
        )

    def _record_app_voice_begin(self, session: _AppVoiceSession) -> None:
        if (
            self._pending_session is not None
            and self._pending_session.session_id != session.session_id
        ):
            self._protocol.end_voice(self._pending_session.session_id)
        self._acknowledge_voice_begin(session)
        self._logger.info(
            "Android app requested voice input: "
            f"session_id={session.session_id} "
            f"package={session.package_name or 'unknown'}"
        )
        if self._waiting_session is not None and not self._waiting_session.done():
            self._waiting_session.set_result(session)
            return
        self._pending_session = session

    def _acknowledge_voice_begin(self, session: _AppVoiceSession) -> None:
        from androidtvremote2.remotemessage_pb2 import RemoteMessage

        begin = RemoteMessage()
        begin.remote_voice_begin.session_id = session.session_id
        self._protocol._send_message(begin)

    @staticmethod
    def _get_protocol(remote: Any) -> Any:
        protocol = getattr(remote, "_remote_message_protocol", None)
        if protocol is None:
            raise RuntimeError("Android TV remote protocol is unavailable")
        return protocol


class _NativeAppVoiceSessionBroker:
    def __init__(self, protocol: Any) -> None:
        self._protocol = protocol

    async def start_voice(self, timeout: float = 2.0):
        return await self._protocol.start_app_voice(timeout)

    def has_pending_session(self) -> bool:
        has_pending_session = getattr(self._protocol, "has_pending_app_voice", None)
        if has_pending_session is None:
            return False
        return bool(has_pending_session())
