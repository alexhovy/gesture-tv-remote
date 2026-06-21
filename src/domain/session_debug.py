import math

from src.domain.constants import DEBUG_NONE, DEBUG_UNKNOWN
from src.domain.landmarks import hand_upright_metrics, hand_upright_reason
from src.domain.session_types import HandState


class GestureSessionDebugMixin:
    def _debug_hands(
        self,
        hands: list[HandState],
        primary_anchor: tuple[float, float] | None,
    ) -> str:
        if not hands:
            return "hand_details=[]"

        details = [
            self._debug_hand(index, hand, primary_anchor)
            for index, hand in enumerate(hands)
        ]
        return f"hand_details=[{';'.join(details)}]"

    def _debug_hand(
        self,
        index: int,
        hand: HandState,
        primary_anchor: tuple[float, float] | None,
    ) -> str:
        center_x, center_y = hand.center
        distance = "none"
        if primary_anchor is not None:
            distance_value = math.hypot(
                center_x - primary_anchor[0],
                center_y - primary_anchor[1],
            )
            distance = f"{distance_value:.2f}"
        dx, dy, tilt_ratio = hand_upright_metrics(hand.landmarks)
        tilt = "inf" if math.isinf(tilt_ratio) else f"{tilt_ratio:.2f}"
        reason = hand_upright_reason(
            hand.landmarks,
            self._config.hand_upright_max_tilt_ratio,
        )

        return (
            f"{index}:gesture={hand.gesture or DEBUG_UNKNOWN}"
            f":upright={hand.upright}"
            f":upright_reason={reason}"
            f":upright_dx={dx:.2f}"
            f":upright_dy={dy:.2f}"
            f":upright_tilt={tilt}"
            f":center=({center_x:.2f},{center_y:.2f})"
            f":size={hand.size:.2f}"
            f":primary_dist={distance}"
        )

    def _debug_pointer_state(self, current_position: tuple[float, float] | None) -> str:
        anchor = self._debug_position(self.pointer_anchor_position)
        current = self._debug_position(current_position)
        dx, dy = self._debug_delta(self.pointer_anchor_position, current_position)
        return (
            f"anchor={anchor}:active={self.pointer_active_gesture or DEBUG_NONE}"
            f":phase={self.pointer_phase}"
            f":armed={self.pointer_armed}"
            f":settle_frames={self.pointer_neutral_frames}"
            f":current={current}:dx={dx}:dy={dy}"
            f":candidate={self.pointer_candidate_gesture or DEBUG_NONE}"
            f":magnitude={self.pointer_candidate_magnitude:.3f}"
            f":activation={self.pointer_activation_distance:.3f}"
            f":neutral={self.pointer_neutral_distance:.3f}"
            f":threshold_ratio={self.pointer_threshold_ratio:.2f}"
            f":in_neutral={self.pointer_in_neutral}"
            f":blocked={self.pointer_last_blocked_reason or DEBUG_NONE}"
        )

    def _debug_volume_state(self) -> str:
        anchor = DEBUG_NONE if self.volume_anchor_y is None else f"{self.volume_anchor_y:.2f}"
        return (
            f"anchor={anchor}:active={self.volume_active_gesture or DEBUG_NONE}"
            f":phase={self.volume_phase}"
            f":armed={self.volume_armed}"
            f":settle_frames={self.volume_neutral_frames}"
            f":candidate={self.volume_candidate_gesture or DEBUG_NONE}"
            f":magnitude={self.volume_candidate_magnitude:.3f}"
            f":activation={self.volume_activation_distance:.3f}"
            f":neutral={self.volume_neutral_distance:.3f}"
            f":threshold_ratio={self.volume_threshold_ratio:.2f}"
            f":in_neutral={self.volume_in_neutral}"
            f":blocked={self.volume_last_blocked_reason or DEBUG_NONE}"
        )

    @staticmethod
    def _debug_position(position: tuple[float, float] | None) -> str:
        if position is None:
            return DEBUG_NONE

        x, y = position
        return f"({x:.2f},{y:.2f})"

    @staticmethod
    def _debug_delta(
        start_position: tuple[float, float] | None,
        current_position: tuple[float, float] | None,
    ) -> tuple[str, str]:
        if start_position is None or current_position is None:
            return DEBUG_NONE, DEBUG_NONE

        start_x, start_y = start_position
        current_x, current_y = current_position
        return f"{current_x - start_x:.2f}", f"{current_y - start_y:.2f}"
