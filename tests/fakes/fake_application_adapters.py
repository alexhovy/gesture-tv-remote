from typing import Any

from src.domain.camera_geometry import CroppedFrame, CropRect
from src.shared.config import AppConfig


class FakeCamera:
    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.crop = CropRect(0.0, 0.0, 1.0, 1.0)

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def current_crop(self) -> CropRect:
        return self.crop

    def detection_crop(self) -> CropRect:
        return self.crop

    def update(self, landmarks_by_hand, crop: CropRect) -> bool:
        return True

    def update_if_current_crop_needs_landmarks(
        self,
        landmarks_by_hand,
        crop: CropRect,
    ) -> bool:
        return True


class FakeFrameProcessor:
    def flip_frame(self, frame: Any) -> Any:
        return frame

    def detection_frame(self, frame: Any, camera: FakeCamera) -> CroppedFrame:
        return CroppedFrame(frame, camera.detection_crop())

    def display_frame(self, frame: Any, camera: FakeCamera) -> CroppedFrame:
        return CroppedFrame(frame, camera.current_crop())

    def close(self) -> None:
        pass


class FakeDisplay:
    def __init__(self, quit_after_render: bool = True) -> None:
        self.quit_after_render = quit_after_render
        self.rendered = 0
        self.closed = False

    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        del detection_crop, display_crop, zoom_frozen
        return decision_debug_message

    def draw_detected_hands(
        self, frame, detected_hands, source_crop, display_crop
    ) -> None:
        pass

    def draw_pointer_zones(self, frame, pointer_debug, display_crop) -> None:
        pass

    def draw_volume_zones(self, frame, volume_debug, display_crop) -> None:
        pass

    def render(self, app_name: str, frame: Any) -> bool:
        del app_name, frame
        self.rendered += 1
        return self.quit_after_render

    def close(self) -> None:
        self.closed = True


class FakeVoiceCapture:
    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.captures = 0

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    async def capture(self) -> None:
        self.captures += 1


class FakeCommandDispatcher:
    queue_depth = 0
    dropped_commands = 0
    last_send_latency_seconds = None

    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self.enqueued: list[tuple[str, str]] = []

    def start(self) -> None:
        self.started = True

    def enqueue(self, gesture: str, command: str) -> None:
        self.enqueued.append((gesture, command))

    async def close(self) -> None:
        self.closed = True
