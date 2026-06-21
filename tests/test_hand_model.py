import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.infrastructure.hand_tracking.hand_model import download_model_if_missing
from tests.config_helpers import app_config


class HandModelDownloadTests(unittest.TestCase):
    def test_download_writes_temp_file_then_replaces_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_file = Path(directory) / "hand.task"
            config = app_config(
                model_file=model_file,
                model_url="https://example.test/model",
                model_download_timeout_seconds=1.0,
                model_download_retries=0,
            )

            with patch(
                "src.infrastructure.hand_tracking.hand_model.urllib.request.urlopen",
                return_value=FakeResponse([b"abc", b"def"]),
            ) as urlopen:
                download_model_if_missing(config)

            self.assertEqual(model_file.read_bytes(), b"abcdef")
            self.assertFalse((Path(directory) / "hand.task.tmp").exists())
            urlopen.assert_called_once_with(
                "https://example.test/model",
                timeout=1.0,
            )

    def test_download_retries_and_removes_partial_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_file = Path(directory) / "hand.task"
            config = app_config(
                model_file=model_file,
                model_url="https://example.test/model",
                model_download_timeout_seconds=1.0,
                model_download_retries=1,
            )
            calls = [
                RuntimeError("network"),
                FakeResponse([b"ok"]),
            ]

            def fake_urlopen(url, timeout):
                result = calls.pop(0)
                if isinstance(result, Exception):
                    raise result
                return result

            with patch(
                "src.infrastructure.hand_tracking.hand_model.urllib.request.urlopen",
                side_effect=fake_urlopen,
            ):
                download_model_if_missing(config)

            self.assertEqual(model_file.read_bytes(), b"ok")
            self.assertFalse((Path(directory) / "hand.task.tmp").exists())


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        pass

    def read(self, size: int) -> bytes:
        del size
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


if __name__ == "__main__":
    unittest.main()
