import asyncio
import unittest

from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    CapabilityStatus,
    TextInputCapabilities,
    TextInputHandler,
    TextInputMode,
    TextInputStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
)
from src.application.services.text_input_service import TextInputService
from src.domain.constants import TV_COMMAND_BACK, TV_COMMAND_DPAD_CENTER


class TextInputServiceTests(unittest.TestCase):
    def test_status_tracks_remote_callback(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)

        remote.emit_status(TextInputStatus(active=True, mode=TextInputMode.MANUAL))

        self.assertTrue(service.status().active)

    def test_send_forwards_supported_text(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)

        result = asyncio.run(service.send("search"))

        self.assertTrue(result.accepted)
        self.assertEqual(remote.actions, [("send", "search")])

    def test_send_uses_append_even_when_replace_is_supported(self) -> None:
        remote = FakeTextRemote(replace_text=CapabilityStatus.IMPLEMENTED)
        service = TextInputService(remote)

        first = asyncio.run(service.send("s"))
        second = asyncio.run(service.send("e"))

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(remote.actions, [("send", "s"), ("send", "e")])

    def test_replace_is_explicit_when_supported(self) -> None:
        remote = FakeTextRemote(replace_text=CapabilityStatus.IMPLEMENTED)
        service = TextInputService(remote)

        result = asyncio.run(service.replace("search"))

        self.assertTrue(result.accepted)
        self.assertEqual(remote.actions, [("replace", "search")])

    def test_delete_forwards_delete_even_when_replace_is_supported(self) -> None:
        remote = FakeTextRemote(replace_text=CapabilityStatus.IMPLEMENTED)
        service = TextInputService(remote)

        result = asyncio.run(service.delete(2))

        self.assertTrue(result.accepted)
        self.assertEqual(remote.actions, [("delete", "2")])

    def test_sync_replaces_full_value_when_replace_is_supported(self) -> None:
        remote = FakeTextRemote(replace_text=CapabilityStatus.IMPLEMENTED)
        service = TextInputService(remote)

        result = asyncio.run(service.sync("search"))

        self.assertTrue(result.accepted)
        self.assertEqual(remote.actions, [("replace", "search")])

    def test_sync_replays_full_value_for_append_only_remote(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)

        first = asyncio.run(service.sync("ab"))
        second = asyncio.run(service.sync("abc"))

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(
            remote.actions,
            [("send", "ab"), ("delete", "2"), ("send", "abc")],
        )

    def test_sync_clears_append_only_remote_when_text_is_empty(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)

        asyncio.run(service.sync("ab"))
        result = asyncio.run(service.sync(""))

        self.assertTrue(result.accepted)
        self.assertEqual(remote.actions, [("send", "ab"), ("delete", "2")])

    def test_send_rejects_unsupported_text(self) -> None:
        remote = FakeTextRemote(send_text=CapabilityStatus.UNSUPPORTED)
        service = TextInputService(remote)

        result = asyncio.run(service.send("search"))

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "unsupported")
        self.assertEqual(remote.actions, [])

    def test_subscriber_receives_status_updates(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)
        statuses: list[TextInputStatus] = []

        unsubscribe = service.subscribe(statuses.append)
        remote.emit_status(TextInputStatus(active=True, mode=TextInputMode.MANUAL))
        unsubscribe()
        remote.emit_status(TextInputStatus(active=False, mode=TextInputMode.MANUAL))

        self.assertEqual([status.active for status in statuses], [False, True])

    def test_dismiss_for_command_clears_active_status(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)
        statuses: list[TextInputStatus] = []
        service.subscribe(statuses.append)
        remote.emit_status(TextInputStatus(active=True, mode=TextInputMode.MANUAL))

        service.dismiss_for_command(TV_COMMAND_BACK)

        self.assertFalse(service.status().active)
        self.assertEqual([status.active for status in statuses], [False, True, False])

    def test_dismiss_for_command_clears_manual_synced_text(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)

        asyncio.run(service.sync("ab"))
        service.dismiss_for_command(TV_COMMAND_BACK)
        asyncio.run(service.sync("c"))

        self.assertEqual(remote.actions, [("send", "ab"), ("send", "c")])

    def test_dismiss_for_command_keeps_active_for_select(self) -> None:
        remote = FakeTextRemote()
        service = TextInputService(remote)
        remote.emit_status(TextInputStatus(active=True, mode=TextInputMode.MANUAL))

        service.dismiss_for_command(TV_COMMAND_DPAD_CENTER)

        self.assertTrue(service.status().active)


class FakeTextRemote:
    def __init__(
        self,
        *,
        send_text: CapabilityStatus = CapabilityStatus.IMPLEMENTED,
        replace_text: CapabilityStatus = CapabilityStatus.UNSUPPORTED,
    ) -> None:
        self._send_text = send_text
        self._replace_text = replace_text
        self._status = TextInputStatus(active=False, mode=TextInputMode.MANUAL)
        self._handler: TextInputHandler | None = None
        self.actions: list[tuple[str, str]] = []

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(),
            power=CapabilityStatus.UNSUPPORTED,
            volume=CapabilityStatus.UNSUPPORTED,
            directional_navigation=CapabilityStatus.UNSUPPORTED,
            media_controls=CapabilityStatus.UNSUPPORTED,
            text_input=TextInputCapabilities(
                focus_detection=CapabilityStatus.UNSUPPORTED,
                send_text=self._send_text,
                replace_text=self._replace_text,
                delete_text=CapabilityStatus.IMPLEMENTED,
                submit_text=CapabilityStatus.UNSUPPORTED,
            ),
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.UNSUPPORTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
            ),
            connection_type="fake",
        )

    def set_text_input_handler(self, handler: TextInputHandler | None) -> None:
        self._handler = handler

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        del handler

    def text_input_status(self) -> TextInputStatus:
        return self._status

    def emit_status(self, status: TextInputStatus) -> None:
        self._status = status
        if self._handler is not None:
            self._handler(status)

    async def send_text(self, text: str) -> None:
        self.actions.append(("send", text))

    async def replace_text(self, text: str) -> None:
        self.actions.append(("replace", text))

    async def delete_text(self, count: int = 1) -> None:
        self.actions.append(("delete", str(count)))

    async def submit_text(self) -> None:
        self.actions.append(("submit", ""))

    async def connect(self) -> bool:
        return True

    async def wake(self) -> bool:
        return True

    async def discover_mac_address(self) -> str | None:
        return None

    async def send_command(self, command: str) -> None:
        del command

    async def start_voice(self, mode) -> None:
        del mode

    async def disconnect(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
