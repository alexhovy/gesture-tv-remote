from typing import Any

from src.application.ports.display import DisplayPort
from src.application.ports.hand_tracker import DetectedHand
from src.application.ports.logger import LoggerPort
from src.domain.geometry.camera_geometry import CropRect
from src.domain.session.session_types import GestureDecision
from src.shared.config import AppConfig


class DisplayDebugCoordinator:
    def __init__(self, display: DisplayPort, logger: LoggerPort) -> None:
        self._display = display
        self._logger = logger
        self._last_debug_time = 0.0
        self._last_debug_message = ""

    def render(
        self,
        *,
        config: AppConfig,
        frame: Any,
        detected_hands: list[DetectedHand],
        detection_crop: CropRect,
        display_crop: CropRect,
        decision: GestureDecision,
        now: float,
    ) -> bool:
        self._log_debug_message(
            config,
            decision,
            detection_crop,
            display_crop,
            now,
        )
        self._display.draw_detected_hands(
            frame,
            detected_hands,
            detection_crop,
            display_crop,
        )
        self._display.draw_pointer_zones(
            frame,
            decision.pointer_debug,
            display_crop,
        )
        self._display.draw_volume_zones(
            frame,
            decision.volume_debug,
            display_crop,
        )
        return self._display.render(config.app_name, frame)

    def _log_debug_message(
        self,
        config: AppConfig,
        decision: GestureDecision,
        detection_crop: CropRect,
        display_crop: CropRect,
        now: float,
    ) -> None:
        debug_message = self._display.debug_message(
            decision.debug_message,
            detection_crop,
            display_crop,
            decision.freeze_zoom,
        )
        if (
            debug_message == self._last_debug_message
            and now - self._last_debug_time < config.debug.log_seconds
        ):
            return

        self._logger.debug(debug_message)
        self._last_debug_message = debug_message
        self._last_debug_time = now
