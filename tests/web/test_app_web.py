import asyncio
import unittest
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any

from aiohttp.test_utils import make_mocked_request

from src.shared.config import AppConfig
from src.web.app import create_web_app


class WebAppRouteTests(unittest.TestCase):
    def test_app_serves_shared_static_directory(self) -> None:
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=FakeTextInput(),
            logger=FakeLogger(),
        )

        route_names = {resource.name for resource in app.router.resources()}

        self.assertIn("static", route_names)

    def test_home_route_renders_destination_hub(self) -> None:
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(app_name="Gesture Test"),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=FakeTextInput(),
            logger=FakeLogger(),
        )
        request = make_mocked_request("GET", "/", app=app)

        handler = _handler_for(app, "/")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertIn("Gesture Test", response.text)
        self.assertIn('href="/gesture"', response.text)
        self.assertIn('href="/remote"', response.text)
        self.assertIn('href="/settings"', response.text)

    def test_restart_route_requests_runtime_restart(self) -> None:
        runtime_control = FakeRuntimeControl()
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=FakeTextInput(),
            logger=FakeLogger(),
            runtime_control=runtime_control,
        )
        request = make_mocked_request("POST", "/restart", app=app)

        handler = _handler_for(app, "/restart")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertTrue(runtime_control.restart_requested)

    def test_remote_capabilities_exposes_supported_command_groups(self) -> None:
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=FakeTextInput(),
            logger=FakeLogger(),
        )
        request = make_mocked_request("GET", "/api/remote/capabilities", app=app)

        handler = _handler_for(app, "/api/remote/capabilities")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertIn('"supportedCommands": ["HOME"]', response.text)
        self.assertIn('"navigation": ["HOME"]', response.text)
        self.assertIn('"sendText": "implemented"', response.text)
        self.assertIn('"browserCapture": "auto_focus"', response.text)

    def test_remote_text_route_sends_text(self) -> None:
        text_input = FakeTextInput()
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=text_input,
            logger=FakeLogger(),
        )
        request = make_mocked_request("POST", "/api/remote/text", app=app)
        request._read_bytes = b'{"text": "hello"}'

        handler = _handler_for(app, "/api/remote/text")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertEqual(text_input.sent, ["hello"])

    def test_remote_text_sync_route_syncs_full_text(self) -> None:
        text_input = FakeTextInput()
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=text_input,
            logger=FakeLogger(),
        )
        request = make_mocked_request("POST", "/api/remote/text/sync", app=app)
        request._read_bytes = b'{"text": "hello"}'

        handler = _handler_for(app, "/api/remote/text/sync")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertEqual(text_input.synced, ["hello"])

    def test_remote_page_has_keyboard_overlay_without_keyboard_controls(
        self,
    ) -> None:
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=FakeTextInput(),
            logger=FakeLogger(),
        )
        request = make_mocked_request("GET", "/remote", app=app)

        handler = _handler_for(app, "/remote")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertIn('id="tv-keyboard-overlay"', response.text)
        self.assertIn('id="tv-keyboard-capture"', response.text)
        self.assertIn('placeholder="TV text"', response.text)
        self.assertIn("/static/text-input.js", response.text)
        self.assertNotIn("keyboard-open", response.text)
        self.assertNotIn("keyboard-submit", response.text)
        self.assertNotIn("keyboard-delete", response.text)

    def test_gesture_page_has_keyboard_overlay(self) -> None:
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            text_input=FakeTextInput(),
            logger=FakeLogger(),
        )
        request = make_mocked_request("GET", "/gesture", app=app)

        handler = _handler_for(app, "/gesture")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertIn('id="tv-keyboard-overlay"', response.text)
        self.assertIn('id="tv-keyboard-capture"', response.text)
        self.assertIn('placeholder="TV text"', response.text)
        self.assertIn("/static/text-input.js", response.text)


class FakeRepository:
    def get_config(self) -> AppConfig | None:
        return None

    def save_config(self, config: AppConfig) -> None:
        del config

    def reset_config(self) -> None:
        pass


class FakeBrowserVideoSink:
    def submit_frame(self, frame: Any) -> None:
        del frame


class FakeBrowserAudioSink:
    async def push_chunk(self, chunk: bytes) -> None:
        del chunk


class FakeDebugSource:
    def subscribe(self) -> Any:
        raise NotImplementedError

    def close(self) -> None:
        pass


class FakeDirectRemote:
    def capabilities(self) -> Any:
        return SimpleNamespace(
            supported_commands=("HOME",),
            command_groups={"navigation": ("HOME",)},
        )

    def supported_commands(self) -> tuple[str, ...]:
        return ()

    def dispatch(self, command: str) -> Any:
        del command
        raise NotImplementedError


class FakeTextInput:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.synced: list[str] = []

    def capabilities(self) -> Any:
        return SimpleNamespace(
            focus_detection=SimpleNamespace(value="unsupported"),
            send_text=SimpleNamespace(value="implemented"),
            replace_text=SimpleNamespace(value="unsupported"),
            delete_text=SimpleNamespace(value="implemented"),
            submit_text=SimpleNamespace(value="implemented"),
            browser_capture=SimpleNamespace(value="auto_focus"),
            notes=(),
        )

    def status(self) -> Any:
        return SimpleNamespace(
            active=False,
            mode=SimpleNamespace(value="manual"),
            value="",
            label="",
            app_id="",
        )

    def subscribe(self, subscriber) -> Any:
        subscriber(self.status())
        return lambda: None

    def dismiss_for_command(self, command: str) -> None:
        del command

    async def send(self, text: str) -> Any:
        self.sent.append(text)
        return SimpleNamespace(accepted=True, reason=None)

    async def replace(self, text: str) -> Any:
        del text
        return SimpleNamespace(accepted=False, reason="unsupported")

    async def delete(self, count: int = 1) -> Any:
        del count
        return SimpleNamespace(accepted=True, reason=None)

    async def sync(self, text: str) -> Any:
        self.synced.append(text)
        return SimpleNamespace(accepted=True, reason=None)

    async def submit(self) -> Any:
        return SimpleNamespace(accepted=True, reason=None)


class FakeRuntimeControl:
    def __init__(self) -> None:
        self.restart_requested = False

    def request_restart(self) -> None:
        self.restart_requested = True


def _handler_for(app, path: str):
    for resource in app.router.resources():
        if resource.canonical == path:
            route = next(iter(resource))
            return route.handler
    raise AssertionError(f"Route not found: {path}")


class FakeLogger:
    def info(self, message: str) -> None:
        del message

    def error(self, message: str) -> None:
        del message

    def debug(self, message: str) -> None:
        del message


if __name__ == "__main__":
    unittest.main()
