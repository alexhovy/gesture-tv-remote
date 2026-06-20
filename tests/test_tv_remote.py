import asyncio
import unittest
from unittest.mock import patch

from src.domain.constants import (
    TV_COMMAND_BACK,
    TV_COMMAND_DPAD_CENTER,
    TV_COMMAND_DPAD_DOWN,
    TV_COMMAND_DPAD_LEFT,
    TV_COMMAND_DPAD_RIGHT,
    TV_COMMAND_DPAD_UP,
    TV_COMMAND_HOME,
    TV_COMMAND_VOLUME_DOWN,
    TV_COMMAND_VOLUME_UP,
)
from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.androidtv_remote import AndroidTvRemoteClient
from src.infrastructure.tv.roku_remote import RokuRemoteClient
from src.infrastructure.tv.samsung_remote import SamsungTvRemoteClient
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import (
    TV_ADAPTER_ANDROIDTV,
    TV_ADAPTER_ROKU,
    TV_ADAPTER_SAMSUNG,
    TV_ADAPTER_WEBOS,
    TvRemoteCommandError,
)
from src.infrastructure.tv.tv_remote_factory import create_tv_remote_client
from src.infrastructure.tv.webos_remote import WebOsRemoteClient
from src.shared.config import AppConfig


class TvRemoteTests(unittest.TestCase):
    def test_factory_creates_selected_adapter(self) -> None:
        cases = [
            (TV_ADAPTER_ANDROIDTV, AndroidTvRemoteClient),
            (TV_ADAPTER_SAMSUNG, SamsungTvRemoteClient),
            (TV_ADAPTER_WEBOS, WebOsRemoteClient),
            (TV_ADAPTER_ROKU, RokuRemoteClient),
        ]

        for adapter, expected_type in cases:
            with self.subTest(adapter=adapter):
                client = create_tv_remote_client(AppConfig(tv_adapter=adapter))
                self.assertIsInstance(client, expected_type)

    def test_factory_rejects_unknown_adapter(self) -> None:
        with self.assertRaises(ValueError):
            create_tv_remote_client(AppConfig(tv_adapter="unknown"))

    def test_translation_covers_all_commands_for_each_adapter(self) -> None:
        commands = [
            TV_COMMAND_HOME,
            TV_COMMAND_BACK,
            TV_COMMAND_DPAD_CENTER,
            TV_COMMAND_DPAD_LEFT,
            TV_COMMAND_DPAD_RIGHT,
            TV_COMMAND_DPAD_UP,
            TV_COMMAND_DPAD_DOWN,
            TV_COMMAND_VOLUME_UP,
            TV_COMMAND_VOLUME_DOWN,
        ]

        for adapter in [
            TV_ADAPTER_ANDROIDTV,
            TV_ADAPTER_SAMSUNG,
            TV_ADAPTER_WEBOS,
            TV_ADAPTER_ROKU,
        ]:
            with self.subTest(adapter=adapter):
                translated = [
                    translate_tv_command(adapter, command)
                    for command in commands
                ]
                self.assertTrue(all(translated))

    def test_translation_rejects_unknown_command(self) -> None:
        with self.assertRaises(TvRemoteCommandError):
            translate_tv_command(TV_ADAPTER_ROKU, "UNKNOWN")


class AsyncRemoteCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_remote_method_uses_thread_offload(self) -> None:
        calls = []

        async def fake_to_thread(method, *args, **kwargs):
            calls.append((method, args, kwargs))
            return method(*args, **kwargs)

        def sync_method(command: str) -> str:
            return command

        with patch("src.infrastructure.tv.async_call.asyncio.to_thread", fake_to_thread):
            result = await call_remote_method(sync_method, "KEY_HOME")

        self.assertEqual(result, "KEY_HOME")
        self.assertEqual(calls, [(sync_method, ("KEY_HOME",), {})])

    async def test_async_remote_method_is_awaited(self) -> None:
        async def async_method() -> str:
            await asyncio.sleep(0)
            return "ok"

        with patch("src.infrastructure.tv.async_call.asyncio.to_thread") as to_thread:
            self.assertEqual(await call_remote_method(async_method), "ok")

        to_thread.assert_not_called()

if __name__ == "__main__":
    unittest.main()
