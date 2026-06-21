import math
from dataclasses import dataclass

from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_BACK,
    GESTURE_PINCH,
    GESTURE_POINT,
)
from src.domain.motion_filter import JoystickDecision
from src.domain.session_types import HandState
from src.shared.config import AppConfig


@dataclass
class ActivationTracker:
    position: tuple[float, float] | None = None
    last_seen_time: float | None = None
    previous_gesture: str | None = None

    def reset(self) -> None:
        self.position = None
        self.last_seen_time = None
        self.previous_gesture = None

    def update_seen(self, hand: HandState, now: float) -> None:
        self.position = hand.center
        self.last_seen_time = now

    def missing_within_grace(self, config: AppConfig, now: float) -> bool:
        if self.position is None or self.last_seen_time is None:
            return False
        grace_seconds = max(0.0, config.gesture.primary_lost_grace_seconds)
        return now - self.last_seen_time <= grace_seconds

    def find_primary_index(self, hands: list[HandState], config: AppConfig) -> int | None:
        if not hands:
            return None
        if self.position is None:
            return next(
                (
                    index
                    for index, hand in enumerate(hands)
                    if hand.upright and hand.gesture == GESTURE_OPEN_PALM
                ),
                None,
            )

        max_distance = max(0.0, config.gesture.primary_match_max_distance)
        candidates = [
            index for index, hand in enumerate(hands)
            if self.distance_from_primary(hand) <= max_distance
        ]
        if not candidates:
            return None

        upright_candidates = [index for index in candidates if hands[index].upright]
        if not upright_candidates:
            return min(candidates, key=lambda index: self.distance_from_primary(hands[index]))

        if self.previous_gesture is None:
            return min(
                upright_candidates,
                key=lambda index: self.distance_from_primary(hands[index]),
            )

        same_gesture = [
            index
            for index in upright_candidates
            if hands[index].gesture == self.previous_gesture
        ]
        if same_gesture:
            return min(same_gesture, key=lambda index: self.distance_from_primary(hands[index]))

        primary_like = [
            index
            for index in upright_candidates
            if hands[index].gesture in {GESTURE_OPEN_PALM, GESTURE_FIST}
        ]
        if primary_like:
            return min(primary_like, key=lambda index: self.distance_from_primary(hands[index]))

        return None

    def distance_from_primary(self, hand: HandState) -> float:
        if self.position is None:
            return math.inf
        target_x, target_y = self.position
        return math.hypot(hand.center[0] - target_x, hand.center[1] - target_y)


@dataclass
class SecondaryGestureInterpreter:
    last_motion_gesture: str | None = None
    last_motion_time: float | None = None
    last_seen_time: float | None = None
    motion_grace_seconds: float = 0.6

    def reset(self) -> None:
        self.last_motion_gesture = None
        self.last_motion_time = None
        self.last_seen_time = None

    def record_seen(self, now: float) -> None:
        self.last_seen_time = now

    def effective_motion_gesture(self, secondary_gesture: str | None, now: float) -> str | None:
        if secondary_gesture in {GESTURE_PINCH, GESTURE_POINT}:
            self.last_motion_gesture = secondary_gesture
            self.last_motion_time = now
            return secondary_gesture

        if (
            secondary_gesture == DEBUG_UNKNOWN
            and self.last_motion_gesture is not None
            and self.last_motion_time is not None
            and now - self.last_motion_time <= self.motion_grace_seconds
        ):
            return self.last_motion_gesture

        return None

    def missing_within_grace(self, now: float) -> bool:
        return (
            self.last_seen_time is not None
            and now - self.last_seen_time <= self.motion_grace_seconds
        )

    def zoom_freeze_reason(self, secondary_hand: HandState | None, now: float) -> str:
        if secondary_hand is not None:
            return "secondary_present"
        if self.missing_within_grace(now):
            return "secondary_grace"
        return "none"


@dataclass
class CommandDecision:
    primary_close_time: float | None = None
    secondary_close_time: float | None = None
    primary_select_pending: bool = False
    secondary_back_pending: bool = False

    def reset(self) -> None:
        self.primary_close_time = None
        self.secondary_close_time = None
        self.primary_select_pending = False
        self.secondary_back_pending = False

    def evaluate(
        self,
        primary_previous_gesture: str | None,
        primary_gesture: str | None,
        secondary_previous_gesture: str | None,
        secondary_gesture: str | None,
        now: float,
        home_chord_seconds: float,
    ) -> str | None:
        primary_closed = (
            primary_previous_gesture == GESTURE_OPEN_PALM
            and primary_gesture == GESTURE_FIST
        )
        secondary_closed = (
            secondary_previous_gesture == GESTURE_OPEN_PALM
            and secondary_gesture == GESTURE_FIST
        )

        if primary_closed:
            self.primary_close_time = now
            self.primary_select_pending = True
        if secondary_closed:
            self.secondary_close_time = now
            self.secondary_back_pending = True

        both_closed = (
            self.primary_close_time is not None
            and self.secondary_close_time is not None
            and abs(self.primary_close_time - self.secondary_close_time)
            <= home_chord_seconds
        )
        if both_closed:
            self.reset()
            return GESTURE_HOME

        if self.primary_select_pending and self.primary_close_time is not None:
            if now - self.primary_close_time > home_chord_seconds:
                self.primary_select_pending = False
                self.primary_close_time = None
                return GESTURE_OPEN_TO_FIST

        if self.secondary_back_pending and self.secondary_close_time is not None:
            if now - self.secondary_close_time > home_chord_seconds:
                self.secondary_back_pending = False
                self.secondary_close_time = None
                return GESTURE_BACK

        return None


@dataclass
class EmitDebounce:
    last_command_time: float = 0.0
    last_command_gesture: str | None = None

    def should_emit(self, command_gesture: str, now: float, debounce_seconds: float) -> bool:
        if command_gesture != self.last_command_gesture:
            return True
        return now - self.last_command_time >= debounce_seconds

    def record_emit(self, command_gesture: str, now: float) -> None:
        self.last_command_time = now
        self.last_command_gesture = command_gesture

    def record_idle(self) -> None:
        self.last_command_gesture = None


@dataclass
class MotionJoystickState:
    anchor: float | tuple[float, float] | None = None
    active_gesture: str | None = None
    armed: bool = True
    neutral_frames: int = 0
    phase: str = "idle"
    last_blocked_reason: str | None = None
    candidate_gesture: str | None = None
    candidate_magnitude: float = 0.0
    activation_distance: float = 0.0
    neutral_distance: float = 0.0
    threshold_ratio: float = 0.0
    in_neutral: bool = True
    position_source: str = "none"

    def reset_tracking(self) -> None:
        self.anchor = None
        self.position_source = "none"
        self.reset_motion_state()

    def reset_motion_state(self) -> None:
        self.active_gesture = None
        self.armed = True
        self.neutral_frames = 0
        self.phase = "armed"

    def reset_diagnostics(self) -> None:
        self.candidate_gesture = None
        self.candidate_magnitude = 0.0
        self.activation_distance = 0.0
        self.neutral_distance = 0.0
        self.threshold_ratio = 0.0
        self.in_neutral = True

    def record_decision(self, decision: JoystickDecision) -> None:
        self.candidate_gesture = decision.gesture
        self.candidate_magnitude = decision.magnitude
        self.activation_distance = decision.activation_distance
        self.neutral_distance = decision.neutral_distance
        self.threshold_ratio = decision.threshold_ratio
        self.in_neutral = decision.in_neutral
        self.last_blocked_reason = decision.blocked_reason

    def command(
        self,
        decision: JoystickDecision,
        current_anchor: float | tuple[float, float],
        settle_frames: int,
    ) -> str | None:
        if decision.in_neutral:
            self.neutral_frames += 1
            self.phase = "settling"
            self.last_blocked_reason = "settling_neutral"
            if self.neutral_frames >= settle_frames:
                self.anchor = current_anchor
                self.reset_motion_state()
            return None

        self.neutral_frames = 0
        if decision.gesture is None:
            if self.armed:
                self.phase = "armed"
            else:
                self.phase = "triggered"
                self.last_blocked_reason = "awaiting_neutral"
            return None

        if self.armed:
            self.active_gesture = decision.gesture
            self.armed = False
            self.phase = "triggered"
            return decision.gesture

        self.phase = "triggered"
        self.last_blocked_reason = "awaiting_neutral"
        return None
