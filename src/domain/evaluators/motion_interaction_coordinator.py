from dataclasses import dataclass

from src.domain.constants import DEBUG_UNKNOWN, GESTURE_PINCH, GESTURE_POINT
from src.domain.evaluators.pointer_evaluator import evaluate_pointer_motion
from src.domain.evaluators.volume_evaluator import evaluate_volume_motion
from src.domain.geometry.landmarks import LANDMARK_INDEX_TIP, landmark_position
from src.domain.session.session_state import GestureSessionState
from src.domain.session.session_types import HandState
from src.shared.config import AppConfig

MOTION_COMMAND_MIN_HAND_SIZE = 0.10
MOTION_COMMAND_GESTURES = {
    GESTURE_PINCH,
    GESTURE_POINT,
}


@dataclass(frozen=True)
class MotionCommandResult:
    command_gesture: str | None = None
    volume_gesture: str | None = None
    pointer_gesture: str | None = None
    volume_distance: float = 0.0
    pointer_distance: float = 0.0
    volume_position: tuple[float, float] | None = None
    pointer_position: tuple[float, float] | None = None


@dataclass(frozen=True)
class MotionPreparation:
    commandable_motion_gesture: str | None
    motion_gesture: str | None
    effective_motion_gesture: str | None


class MotionInteractionCoordinator:
    def prepare(
        self,
        state: GestureSessionState,
        active_gesture: str | None,
        active_size: float,
        pointer_reference_size: float,
        now: float,
    ) -> MotionPreparation:
        commandable = self.commandable_motion_gesture(
            state,
            active_gesture,
            active_size,
            pointer_reference_size,
        )
        motion_gesture = self.motion_gesture(active_gesture, commandable)
        effective = state.motion.effective_motion_gesture(motion_gesture, now)
        return MotionPreparation(
            commandable_motion_gesture=commandable,
            motion_gesture=motion_gesture,
            effective_motion_gesture=effective,
        )

    def evaluate(
        self,
        state: GestureSessionState,
        active_hand: HandState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
        effective_motion_gesture: str | None,
        pointer_reference_size: float,
        config: AppConfig,
        now: float,
    ) -> MotionCommandResult:
        volume_result = self._evaluate_volume_command(
            state,
            active_hand,
            active_gesture,
            commandable_motion_gesture,
            effective_motion_gesture,
            config,
            now,
        )
        if volume_result.command_gesture is not None:
            return volume_result

        pointer_result = self._evaluate_pointer_command(
            state,
            active_hand,
            active_gesture,
            commandable_motion_gesture,
            effective_motion_gesture,
            pointer_reference_size,
            config,
            now,
        )
        if pointer_result.command_gesture is not None:
            return MotionCommandResult(
                command_gesture=pointer_result.command_gesture,
                volume_gesture=volume_result.volume_gesture,
                pointer_gesture=pointer_result.pointer_gesture,
                volume_distance=volume_result.volume_distance,
                pointer_distance=pointer_result.pointer_distance,
                volume_position=volume_result.volume_position,
                pointer_position=pointer_result.pointer_position,
            )

        return MotionCommandResult(
            volume_gesture=volume_result.volume_gesture,
            pointer_gesture=pointer_result.pointer_gesture,
            volume_distance=volume_result.volume_distance,
            pointer_distance=pointer_result.pointer_distance,
            volume_position=volume_result.volume_position,
            pointer_position=pointer_result.pointer_position,
        )

    def commandable_motion_gesture(
        self,
        state: GestureSessionState,
        gesture: str | None,
        hand_size: float,
        reference_size: float,
    ) -> str | None:
        state.pose_blocked_reason = None
        if gesture not in MOTION_COMMAND_GESTURES:
            return None
        if (
            self._relative_hand_size(hand_size, reference_size)
            < MOTION_COMMAND_MIN_HAND_SIZE
        ):
            state.pose_blocked_reason = "hand_too_small"
            return None
        return gesture

    def motion_gesture(
        self,
        gesture: str | None,
        commandable_motion_gesture: str | None,
    ) -> str | None:
        if gesture is None:
            return None
        if gesture == DEBUG_UNKNOWN:
            return DEBUG_UNKNOWN
        if gesture in MOTION_COMMAND_GESTURES:
            if commandable_motion_gesture == gesture:
                return gesture
            return DEBUG_UNKNOWN
        return None

    def _evaluate_volume_command(
        self,
        state: GestureSessionState,
        active_hand: HandState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
        effective_motion_gesture: str | None,
        config: AppConfig,
        now: float,
    ) -> MotionCommandResult:
        pinch_commandable = (
            commandable_motion_gesture == GESTURE_PINCH
            or active_gesture == DEBUG_UNKNOWN
        )
        if effective_motion_gesture == GESTURE_PINCH and pinch_commandable:
            state.pointer.reset_tracking()
            volume = evaluate_volume_motion(
                state.volume,
                active_hand.center,
                active_hand.size,
                config,
                now,
            )
            return MotionCommandResult(
                command_gesture=volume.command_gesture,
                volume_gesture=volume.command_gesture,
                volume_distance=volume.distance,
                volume_position=volume.position,
            )

        if effective_motion_gesture == GESTURE_PINCH:
            state.mark_motion_grace("motion_grace")
        elif effective_motion_gesture != GESTURE_PINCH:
            self._clear_or_grace_volume_tracking(
                state,
                active_gesture,
                commandable_motion_gesture,
            )

        return MotionCommandResult()

    def _evaluate_pointer_command(
        self,
        state: GestureSessionState,
        active_hand: HandState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
        effective_motion_gesture: str | None,
        pointer_reference_size: float,
        config: AppConfig,
        now: float,
    ) -> MotionCommandResult:
        point_commandable = (
            commandable_motion_gesture == GESTURE_POINT
            or active_gesture == DEBUG_UNKNOWN
        )
        if effective_motion_gesture == GESTURE_POINT and point_commandable:
            pointer = evaluate_pointer_motion(
                state.pointer,
                self._pointer_position(state, active_hand),
                pointer_reference_size,
                config,
                now,
            )
            return MotionCommandResult(
                command_gesture=pointer.command_gesture,
                pointer_gesture=pointer.command_gesture,
                pointer_distance=pointer.distance,
                pointer_position=pointer.position,
            )

        if effective_motion_gesture == GESTURE_POINT:
            state.mark_motion_grace("motion_grace")
        elif effective_motion_gesture != GESTURE_POINT:
            self._clear_or_grace_pointer_tracking(
                state,
                active_gesture,
                commandable_motion_gesture,
            )

        return MotionCommandResult()

    def _clear_or_grace_volume_tracking(
        self,
        state: GestureSessionState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
    ) -> None:
        if state.volume.anchor is None:
            state.volume.reset_tracking()
        elif (
            commandable_motion_gesture == GESTURE_POINT
            or self._explicit_non_motion_gesture(active_gesture)
        ):
            state.volume.reset_tracking()
        else:
            state.mark_motion_grace("motion_lost")

    def _clear_or_grace_pointer_tracking(
        self,
        state: GestureSessionState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
    ) -> None:
        if state.pointer.anchor is None:
            state.pointer.reset_tracking()
        elif (
            commandable_motion_gesture == GESTURE_PINCH
            or self._explicit_non_motion_gesture(active_gesture)
        ):
            state.pointer.reset_tracking()
        else:
            state.mark_motion_grace("motion_lost")

    @staticmethod
    def _explicit_non_motion_gesture(gesture: str | None) -> bool:
        return (
            gesture is not None
            and gesture != DEBUG_UNKNOWN
            and gesture not in MOTION_COMMAND_GESTURES
        )

    @staticmethod
    def _relative_hand_size(hand_size: float, reference_size: float) -> float:
        if reference_size <= 0:
            return hand_size
        return hand_size / reference_size

    @staticmethod
    def _pointer_position(
        state: GestureSessionState,
        active_hand: HandState,
    ) -> tuple[float, float]:
        if len(active_hand.landmarks) > LANDMARK_INDEX_TIP:
            state.pointer.position_source = "index_tip"
            return landmark_position(active_hand.landmarks, LANDMARK_INDEX_TIP)

        state.pointer.position_source = "center"
        return active_hand.center
