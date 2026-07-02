import unittest

from src.infrastructure.audio.browser_voice_capture import BrowserAudioSource
from src.infrastructure.camera.browser_frame_source import BrowserFrameSource


class BrowserFrameSourceTests(unittest.TestCase):
    def test_submitted_frame_becomes_latest_versioned_frame(self) -> None:
        source = BrowserFrameSource()
        frame = object()

        source.submit_frame(frame)

        self.assertTrue(source.is_open())
        self.assertFalse(source.failed())
        self.assertEqual(source.latest_versioned(), (1, frame))

    def test_close_clears_latest_frame_and_reports_not_open(self) -> None:
        source = BrowserFrameSource()
        source.submit_frame(object())

        source.close()

        self.assertFalse(source.is_open())
        self.assertEqual(source.latest_versioned(), (1, None))


class BrowserAudioSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_next_chunk_returns_pushed_audio(self) -> None:
        source = BrowserAudioSource()

        await source.push_chunk(b"audio")

        self.assertEqual(await source.next_chunk(timeout=0.01), b"audio")

    async def test_next_chunk_times_out_when_no_audio_is_available(self) -> None:
        source = BrowserAudioSource()

        self.assertIsNone(await source.next_chunk(timeout=0.01))

    async def test_keeps_latest_chunks_when_queue_is_full(self) -> None:
        source = BrowserAudioSource()

        for index in range(20):
            await source.push_chunk(bytes([index]))

        chunks = []
        while True:
            chunk = await source.next_chunk(timeout=0.01)
            if chunk is None:
                break
            chunks.append(chunk)

        self.assertEqual(chunks[0], bytes([8]))
        self.assertEqual(chunks[-1], bytes([19]))
        self.assertEqual(len(chunks), 12)


if __name__ == "__main__":
    unittest.main()
