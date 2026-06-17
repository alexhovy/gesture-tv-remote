import asyncio

from src.services.gesture_remote_service import GestureRemoteService
from src.shared.config import load_config_from_env


async def main() -> None:
    service = GestureRemoteService(load_config_from_env())
    await service.run()


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting.")
