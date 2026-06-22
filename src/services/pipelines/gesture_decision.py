import time

from src.domain.session import GestureSession
from src.domain.session_types import GestureDecision, HandState
from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.landmark_projection import hand_states_to_original_space
from src.infrastructure.camera.video_preprocessing import CropRect
from src.services.pipeline_metrics import PipelineMetrics


class GestureDecisionPipeline:
    def __init__(
        self,
        gesture_session: GestureSession,
        zoom_controller: CameraZoomController,
        metrics: PipelineMetrics | None = None,
    ) -> None:
        self._gesture_session = gesture_session
        self._zoom_controller = zoom_controller
        self._metrics = metrics

    def evaluate(
        self,
        hand_states: list[HandState],
        detection_crop: CropRect,
        display_crop: CropRect,
        now: float,
    ) -> GestureDecision:
        started_at = time.monotonic()
        decision = self._gesture_session.evaluate(
            hand_states_to_original_space(hand_states, detection_crop),
            now,
            pointer_reference_size=min(display_crop.width, display_crop.height),
        )
        if self._metrics is not None:
            self._metrics.record_decision(
                time.monotonic() - started_at,
                decision.command_gesture,
            )
        self.update_zoom(decision)
        return decision

    def update_zoom(self, decision: GestureDecision) -> bool:
        if decision.primary_temporarily_lost:
            return False

        full_frame_crop = CropRect(0.0, 0.0, 1.0, 1.0)
        if not decision.activated:
            return self._zoom_controller.update([], full_frame_crop)

        if decision.freeze_zoom:
            return self._zoom_controller.update_if_current_crop_needs_landmarks(
                decision.zoom_landmarks,
                full_frame_crop,
            )

        return self._zoom_controller.update(decision.zoom_landmarks, full_frame_crop)
