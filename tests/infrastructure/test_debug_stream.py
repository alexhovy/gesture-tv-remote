import asyncio
import unittest

from src.infrastructure.web.debug_stream import BrowserDebugStream


class BrowserDebugStreamTests(unittest.TestCase):
    def test_close_wakes_subscriber(self) -> None:
        async def run() -> None:
            stream = BrowserDebugStream()
            subscription = stream.subscribe()
            task = asyncio.ensure_future(subscription.__anext__())
            await asyncio.sleep(0)

            stream.close()

            with self.assertRaises(StopAsyncIteration):
                await asyncio.wait_for(task, timeout=0.1)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
