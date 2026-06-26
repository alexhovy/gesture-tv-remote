import asyncio
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.application.ports.tv_remote import CapabilityStatus
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
from src.infrastructure.tv.androidtv_remote import AndroidTvRemoteClient
from src.infrastructure.tv.async_call import call_remote_method
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
from tests.helpers.config_helpers import app_config


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
                client = create_tv_remote_client(app_config(tv_adapter=adapter))
                self.assertIsInstance(client, expected_type)

    def test_each_adapter_exposes_capabilities(self) -> None:
        for adapter in [
            TV_ADAPTER_ANDROIDTV,
            TV_ADAPTER_SAMSUNG,
            TV_ADAPTER_WEBOS,
            TV_ADAPTER_ROKU,
        ]:
            with self.subTest(adapter=adapter):
                capabilities = create_tv_remote_client(
                    app_config(tv_adapter=adapter)
                ).capabilities()

                self.assertTrue(capabilities.connection_type)
                self.assertEqual(
                    capabilities.directional_navigation,
                    CapabilityStatus.IMPLEMENTED,
                )
                self.assertEqual(capabilities.volume, CapabilityStatus.IMPLEMENTED)
                self.assertTrue(capabilities.known_limitations)

    def test_capability_status_distinguishes_unsupported_from_not_implemented(
        self,
    ) -> None:
        android_capabilities = create_tv_remote_client(
            app_config(tv_adapter=TV_ADAPTER_ANDROIDTV)
        ).capabilities()
        roku_capabilities = create_tv_remote_client(
            app_config(tv_adapter=TV_ADAPTER_ROKU)
        ).capabilities()

        self.assertEqual(
            android_capabilities.voice_capture, CapabilityStatus.IMPLEMENTED
        )
        self.assertEqual(roku_capabilities.voice_capture, CapabilityStatus.UNSUPPORTED)
        self.assertEqual(roku_capabilities.power, CapabilityStatus.NOT_IMPLEMENTED)
        self.assertEqual(roku_capabilities.pairing, CapabilityStatus.UNSUPPORTED)

    def test_factory_rejects_unknown_adapter(self) -> None:
        with self.assertRaises(ValueError):
            create_tv_remote_client(app_config(tv_adapter="unknown"))

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
                    translate_tv_command(adapter, command) for command in commands
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

        with patch(
            "src.infrastructure.tv.async_call.asyncio.to_thread", fake_to_thread
        ):
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

    async def test_sync_remote_method_returning_awaitable_is_awaited(self) -> None:
        async def fake_to_thread(method, *args, **kwargs):
            return method(*args, **kwargs)

        async def result() -> str:
            return "ok"

        with patch(
            "src.infrastructure.tv.async_call.asyncio.to_thread", fake_to_thread
        ):
            self.assertEqual(await call_remote_method(lambda: result()), "ok")

    async def test_sync_remote_method_can_stay_on_event_loop_thread(self) -> None:
        calls = []

        def sync_method(command: str) -> str:
            calls.append((command, threading.get_ident()))
            return command

        loop_thread_id = threading.get_ident()
        with patch("src.infrastructure.tv.async_call.asyncio.to_thread") as to_thread:
            result = await call_remote_method(
                sync_method,
                "KEY_HOME",
                offload_sync=False,
            )

        self.assertEqual(result, "KEY_HOME")
        self.assertEqual(calls, [("KEY_HOME", loop_thread_id)])
        to_thread.assert_not_called()


class SamsungTvRemoteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._previous_module = sys.modules.get("samsungtvws")

    async def asyncTearDown(self) -> None:
        if self._previous_module is None:
            sys.modules.pop("samsungtvws", None)
        else:
            sys.modules["samsungtvws"] = self._previous_module

    async def test_sync_client_calls_stay_on_one_worker_thread(self) -> None:
        fake_remote = _install_fake_samsung()
        with tempfile.TemporaryDirectory() as temp_dir:
            client = SamsungTvRemoteClient(
                app_config(
                    tv_host="tv.local",
                    samsung_token_file=Path(temp_dir) / "token.txt",
                )
            )

            self.assertTrue(await client.connect())
            await client.send_command(TV_COMMAND_DPAD_LEFT)
            await client.disconnect()

        instance = fake_remote.instances[0]
        thread_ids = {thread_id for _, thread_id in instance.operations}
        self.assertEqual(len(thread_ids), 1)
        self.assertEqual(
            [name for name, _ in instance.operations],
            ["init", "open", "send:KEY_LEFT", "close"],
        )

    async def test_command_reconnects_and_retries_after_socket_failure(self) -> None:
        fake_remote = _install_fake_samsung(fail_first_send=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            client = SamsungTvRemoteClient(
                app_config(
                    tv_host="tv.local",
                    samsung_token_file=Path(temp_dir) / "token.txt",
                )
            )

            self.assertTrue(await client.connect())
            await client.send_command(TV_COMMAND_DPAD_RIGHT)
            await client.disconnect()

        self.assertEqual(len(fake_remote.instances), 2)
        self.assertEqual(
            [name for name, _ in fake_remote.instances[0].operations],
            ["init", "open", "send:KEY_RIGHT", "close"],
        )
        self.assertEqual(
            [name for name, _ in fake_remote.instances[1].operations],
            ["init", "open", "send:KEY_RIGHT", "close"],
        )


class RokuRemoteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._previous_module = sys.modules.get("rokuecp")

    async def asyncTearDown(self) -> None:
        if self._previous_module is None:
            sys.modules.pop("rokuecp", None)
        else:
            sys.modules["rokuecp"] = self._previous_module

    async def test_sync_client_calls_stay_on_one_worker_thread(self) -> None:
        fake_remote = _install_fake_roku()
        client = RokuRemoteClient(app_config(tv_host="roku.local"))

        self.assertTrue(await client.connect())
        await client.send_command(TV_COMMAND_DPAD_UP)
        await client.disconnect()

        instance = fake_remote.instances[0]
        thread_ids = {thread_id for _, thread_id in instance.operations}
        self.assertEqual(len(thread_ids), 1)
        self.assertEqual(
            [name for name, _ in instance.operations],
            ["init", "keypress:Up", "close"],
        )

    async def test_command_reconnects_and_retries_after_socket_failure(self) -> None:
        fake_remote = _install_fake_roku(fail_first_send=True)
        client = RokuRemoteClient(app_config(tv_host="roku.local"))

        self.assertTrue(await client.connect())
        await client.send_command(TV_COMMAND_DPAD_DOWN)
        await client.disconnect()

        self.assertEqual(len(fake_remote.instances), 2)
        self.assertEqual(
            [name for name, _ in fake_remote.instances[0].operations],
            ["init", "keypress:Down", "close"],
        )
        self.assertEqual(
            [name for name, _ in fake_remote.instances[1].operations],
            ["init", "keypress:Down", "close"],
        )


def _install_fake_samsung(fail_first_send: bool = False):
    class FakeSamsungTVWS:
        instances = []
        send_count = 0

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.operations = [("init", threading.get_ident())]
            FakeSamsungTVWS.instances.append(self)

        def open(self):
            self.operations.append(("open", threading.get_ident()))

        def send_key(self, key):
            FakeSamsungTVWS.send_count += 1
            self.operations.append((f"send:{key}", threading.get_ident()))
            if fail_first_send and FakeSamsungTVWS.send_count == 1:
                raise OSError("socket is already closed")

        def close(self):
            self.operations.append(("close", threading.get_ident()))

    module = types.SimpleNamespace(SamsungTVWS=FakeSamsungTVWS)
    sys.modules["samsungtvws"] = module
    return FakeSamsungTVWS


def _install_fake_roku(fail_first_send: bool = False):
    class FakeRoku:
        instances = []
        send_count = 0

        def __init__(self, host, port):
            self.host = host
            self.port = port
            self.operations = [("init", threading.get_ident())]
            FakeRoku.instances.append(self)

        def keypress(self, key):
            FakeRoku.send_count += 1
            self.operations.append((f"keypress:{key}", threading.get_ident()))
            if fail_first_send and FakeRoku.send_count == 1:
                raise OSError("socket is already closed")

        def close(self):
            self.operations.append(("close", threading.get_ident()))

    module = types.SimpleNamespace(Roku=FakeRoku)
    sys.modules["rokuecp"] = module
    return FakeRoku


if __name__ == "__main__":
    unittest.main()
