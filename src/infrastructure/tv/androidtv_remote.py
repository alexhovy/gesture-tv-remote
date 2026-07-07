import asyncio
from dataclasses import dataclass
from types import MethodType
from typing import Any

from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    AppVoiceInputRequest,
    CapabilityStatus,
    TextInputBrowserCapture,
    TextInputCapabilities,
    TextInputHandler,
    TextInputMode,
    TextInputStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)
from src.domain.constants import (
    TV_COMMAND_BACK,
    TV_COMMAND_HOME,
    TV_COMMAND_POWER_OFF,
    TV_COMMAND_POWER_ON,
    TV_COMMAND_POWER_TOGGLE,
)
from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_command_translation import (
    ANDROIDTV_COMMANDS,
    translate_tv_command,
)
from src.infrastructure.tv.tv_remote import TV_ADAPTER_ANDROIDTV
from src.infrastructure.tv.wake_on_lan import WakeOnLanSender, normalize_mac_address
from src.shared.config import AppConfig
from src.shared.logging import AppLogger

_TEXT_DISMISS_COMMANDS = frozenset(
    {
        TV_COMMAND_BACK,
        TV_COMMAND_HOME,
        TV_COMMAND_POWER_OFF,
        TV_COMMAND_POWER_ON,
        TV_COMMAND_POWER_TOGGLE,
    }
)


class AndroidTvRemoteClient:
    def __init__(
        self,
        config: AppConfig,
        wake_on_lan: WakeOnLanSender | None = None,
    ) -> None:
        self._config = config
        self._remote: Any | None = None
        self._logger = AppLogger()
        self._wake_on_lan = wake_on_lan or WakeOnLanSender(config, self._logger)
        self._app_voice_input_handler: AppVoiceInputHandler | None = None
        self._text_input_handler: TextInputHandler | None = None
        self._text_input_status = TextInputStatus(
            active=False,
            mode=TextInputMode.MANUAL,
        )

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(ANDROIDTV_COMMANDS),
            power=CapabilityStatus.IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.IMPLEMENTED,
            text_input=TextInputCapabilities(
                focus_detection=CapabilityStatus.UNSUPPORTED,
                send_text=CapabilityStatus.IMPLEMENTED,
                replace_text=CapabilityStatus.UNSUPPORTED,
                delete_text=CapabilityStatus.IMPLEMENTED,
                submit_text=CapabilityStatus.IMPLEMENTED,
                browser_capture=TextInputBrowserCapture.HARDWARE_KEYS,
                notes=(
                    "Android TV IME negotiation is disabled so the TV does not "
                    "show the remote keyboard handoff prompt.",
                    "Text inserts are sent through the androidtvremote2 text "
                    "API as append-only edits, so text field focus is captured "
                    "manually from the browser.",
                ),
            ),
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.IMPLEMENTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.IMPLEMENTED,
                native_voice_search=CapabilityStatus.IMPLEMENTED,
                app_voice_input=CapabilityStatus.IMPLEMENTED,
                notes=(
                    "Remote microphone streaming uses Android TV Remote Protocol "
                    "voice sessions.",
                    "Foreground app voice input attaches to an app-requested "
                    "voice session without sending global search.",
                ),
            ),
            connection_type="androidtvremote2 TLS remote protocol",
            known_limitations=(
                "Power uses the Android TV power key and may toggle either the "
                "streaming device or attached TV depending on device settings.",
                "Wake-on-LAN sends a generic magic packet when a MAC address is "
                "configured; Android TV model support varies.",
                "Source selection is not mapped.",
            ),
        )

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        self._app_voice_input_handler = handler
        if self._remote is None:
            return
        broker = _AndroidAppVoiceSessionBroker.for_remote(self._remote, self._logger)
        broker.set_app_voice_input_handler(handler)

    def set_text_input_handler(self, handler: TextInputHandler | None) -> None:
        self._text_input_handler = handler

    def text_input_status(self) -> TextInputStatus:
        return self._text_input_status

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
            enable_ime=False,
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
        broker = _AndroidAppVoiceSessionBroker.for_remote(remote, self._logger)
        broker.set_app_voice_input_handler(self._app_voice_input_handler)
        self._logger.info(
            "Android TV text input mode: androidtvremote2_send_text "
            "enable_ime=False focus_detection=manual"
        )
        self._logger.info(f"Connected to Android TV at {self._config.tv.host}")
        return True

    async def wake(self) -> bool:
        try:
            result = await call_remote_method(self._wake_on_lan.wake)
        except Exception as error:
            self._logger.error(f"Android TV Wake-on-LAN failed: {error}")
            return False
        return result.attempted and result.sent_packets > 0

    async def discover_mac_address(self) -> str | None:
        try:
            name, mac_address = await self._remote_name_and_mac()
        except Exception as error:
            self._logger.debug(f"Android TV MAC discovery failed: {error}")
            return None
        normalized = normalize_mac_address(mac_address)
        if normalized is None:
            return None
        self._logger.info(f"Android TV reported device identity for {name}.")
        return normalized

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
            self._dismiss_text_input_for_command(command)
        except ConnectionClosed:
            self._logger.error("Android TV connection closed. Command not sent.")
        except ValueError as error:
            self._logger.error(f"Invalid Android TV command {adapter_command}: {error}")

    async def send_text(self, text: str) -> None:
        if self._remote is None:
            self._logger.info("TV not connected. Skipping Android TV text input.")
            return

        from androidtvremote2 import ConnectionClosed

        try:
            await call_remote_method(
                self._remote.send_text,
                text,
                offload_sync=False,
            )
        except ConnectionClosed:
            self._logger.error("Android TV connection closed. Text not sent.")
        except ValueError as error:
            self._logger.error(f"Invalid Android TV text input: {error}")

    async def replace_text(self, text: str) -> None:
        del text
        self._logger.info("Android TV text replacement is not supported.")

    async def delete_text(self, count: int = 1) -> None:
        for _ in range(count):
            await self._send_android_key("DEL")

    async def submit_text(self) -> None:
        await self._send_android_key("ENTER")

    async def _send_android_key(self, key: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping Android TV key: {key}")
            return
        from androidtvremote2 import ConnectionClosed

        try:
            await call_remote_method(
                self._remote.send_key_command,
                key,
                offload_sync=False,
            )
        except ConnectionClosed:
            self._logger.error(f"Android TV connection closed. Key not sent: {key}")

    async def _remote_name_and_mac(self) -> tuple[str, str]:
        from androidtvremote2 import AndroidTVRemote

        remote = AndroidTVRemote(
            self._config.app_name,
            str(self._config.tv.android_cert_file),
            str(self._config.tv.android_key_file),
            self._config.tv.host,
        )
        return await remote.async_get_name_and_mac()

    async def start_voice(self, mode: VoiceInputMode):
        if self._remote is None:
            return None
        if mode == VoiceInputMode.AUTO:
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

    def _handle_text_input_status(self, status: TextInputStatus) -> None:
        self._text_input_status = status
        if self._text_input_handler is not None:
            self._text_input_handler(status)

    def _dismiss_text_input_for_command(self, command: str) -> None:
        if command not in _TEXT_DISMISS_COMMANDS:
            return
        status = TextInputStatus(
            active=False,
            mode=self._text_input_status.mode,
            label=self._text_input_status.label,
            app_id=self._text_input_status.app_id,
        )
        self._text_input_status = status
        if self._remote is not None:
            broker = _AndroidAppVoiceSessionBroker.for_remote(
                self._remote,
                self._logger,
            )
            broker.record_text_input_dismissed(status)
        elif self._text_input_handler is not None:
            self._text_input_handler(status)


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
        self._app_voice_input_handler: AppVoiceInputHandler | None = None
        self._original_handle_message = self._protocol._handle_message
        self._protocol._handle_message = MethodType(
            _AndroidAppVoiceSessionBroker._handle_message,
            self,
        )
        self._text_input_handler: TextInputHandler | None = None
        self._text_input_status = TextInputStatus(
            active=False,
            mode=TextInputMode.AUTO_DETECTED,
        )

    @classmethod
    def for_remote(
        cls,
        remote: Any,
        logger: AppLogger,
    ) -> "_AndroidAppVoiceSessionBroker":
        broker = getattr(remote, cls._REMOTE_ATTRIBUTE, None)
        if broker is None:
            broker = cls(remote, logger)
            setattr(remote, cls._REMOTE_ATTRIBUTE, broker)
        return broker

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        self._app_voice_input_handler = handler

    def set_text_input_handler(self, handler: TextInputHandler | None) -> None:
        self._text_input_handler = handler

    def text_input_status(self) -> TextInputStatus:
        return self._text_input_status

    def text_input_counters(self) -> tuple[int, int]:
        return (
            int(getattr(self._protocol, "ime_counter", 0)),
            int(getattr(self._protocol, "ime_field_counter", 0)),
        )

    def record_text_input_dismissed(self, status: TextInputStatus) -> None:
        self._text_input_status = status
        handler = self._text_input_handler
        if handler is not None:
            self._loop.call_soon_threadsafe(handler, status)

    def _handle_message(self, raw_msg: bytes) -> None:
        text_input_status = self._parse_text_input_status(raw_msg)
        if text_input_status is not None:
            self._record_text_input_status(text_input_status)
        app_voice_session = self._parse_app_voice_begin(raw_msg)
        if app_voice_session is not None:
            self._record_app_voice_begin(app_voice_session)
        self._original_handle_message(raw_msg)

    def _parse_text_input_status(self, raw_msg: bytes) -> TextInputStatus | None:
        from androidtvremote2.remotemessage_pb2 import RemoteMessage
        from google.protobuf.message import DecodeError

        msg = RemoteMessage()
        try:
            msg.ParseFromString(raw_msg)
        except DecodeError:
            return None
        if msg.HasField("remote_ime_show_request"):
            self._logger.info("Android TV IME message: remote_ime_show_request")
            field_status = msg.remote_ime_show_request.remote_text_field_status
            return TextInputStatus(
                active=True,
                mode=TextInputMode.AUTO_DETECTED,
                value=field_status.value,
                label=field_status.label,
            )
        if msg.HasField("remote_ime_key_inject"):
            self._logger.info("Android TV IME message: remote_ime_key_inject")
            field_status = msg.remote_ime_key_inject.text_field_status
            return TextInputStatus(
                active=True,
                mode=TextInputMode.AUTO_DETECTED,
                value=field_status.value,
                label=field_status.label,
                app_id=msg.remote_ime_key_inject.app_info.app_package,
            )
        if msg.HasField("remote_ime_batch_edit"):
            self._logger.info("Android TV IME message: remote_ime_batch_edit")
            edit_info = msg.remote_ime_batch_edit.edit_info
            if edit_info:
                value = edit_info[-1].text_field_status.value
            else:
                value = self._text_input_status.value
            return TextInputStatus(
                active=True,
                mode=TextInputMode.AUTO_DETECTED,
                value=value,
                label=self._text_input_status.label,
                app_id=self._text_input_status.app_id,
            )
        return None

    def _record_text_input_status(self, status: TextInputStatus) -> None:
        self._text_input_status = status
        self._logger.info(
            "Android TV text input status "
            f"active={status.active} label={status.label or 'unknown'} "
            f"app={status.app_id or 'unknown'} value_length={len(status.value)}"
        )
        handler = self._text_input_handler
        if handler is not None:
            self._loop.call_soon_threadsafe(handler, status)

    def _parse_app_voice_begin(self, raw_msg: bytes) -> _AppVoiceSession | None:
        on_voice_begin = getattr(self._protocol, "_on_voice_begin", None)
        if on_voice_begin is not None and not on_voice_begin.done():
            return None

        from androidtvremote2.remotemessage_pb2 import RemoteMessage
        from google.protobuf.message import DecodeError

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
        self._acknowledge_voice_begin(session)
        self._logger.info(
            "Android app requested voice input: "
            f"session_id={session.session_id} "
            f"package={session.package_name or 'unknown'}"
        )
        handler = self._app_voice_input_handler
        if handler is None:
            self._logger.info("No Android app voice input handler is registered.")
            self._protocol.end_voice(session.session_id)
            return

        request = AppVoiceInputRequest(
            stream=_ProtocolVoiceStream(self._protocol, session),
            session_id=session.session_id,
            package_name=session.package_name,
        )

        def schedule_handler() -> None:
            asyncio.ensure_future(handler(request))

        self._loop.call_soon_threadsafe(schedule_handler)

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
