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
            logger=FakeLogger(),
        )

        route_names = {resource.name for resource in app.router.resources()}

        self.assertIn("static", route_names)

    def test_remote_capabilities_exposes_supported_command_groups(self) -> None:
        app = create_web_app(
            repository=FakeRepository(),
            config_provider=lambda: AppConfig(),
            browser_video_sink=FakeBrowserVideoSink(),
            browser_audio_sink=FakeBrowserAudioSink(),
            debug_source=FakeDebugSource(),
            direct_remote=FakeDirectRemote(),
            logger=FakeLogger(),
        )
        request = make_mocked_request("GET", "/api/remote/capabilities", app=app)

        handler = _handler_for(app, "/api/remote/capabilities")
        response = asyncio.run(handler(request))

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertIn('"supportedCommands": ["HOME"]', response.text)
        self.assertIn('"navigation": ["HOME"]', response.text)


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
