from dataclasses import dataclass, field

from src.domain.constants import DEBUG_UNKNOWN, GESTURE_PINCH, GESTURE_POINT
from src.domain.gesture_history import BoundedHistory
from src.domain.motion_filter import JoystickDecision
from src.domain.session_types import HandState


@dataclass
class SecondaryGestureInterpreter:
    last_motion_gesture: str | None = None
    last_motion_time: float | None = None
    last_seen_time: float | None = None
    motion_grace_seconds: float = 0.6
    recent_motion_gestures: BoundedHistory[tuple[float, str]] = field(
        default_factory=lambda: BoundedHistory[tuple[float, str]](8)
    )

    def reset(self) -> None:
        self.last_motion_gesture = None
        self.last_motion_time = None
        self.last_seen_time = None
        self.recent_motion_gestures.clear()

    def record_seen(self, now: float) -> None:
        self.last_seen_time = now

    def effective_motion_gesture(self, secondary_gesture: str | None, now: float) -> str | None:
        if secondary_gesture in {GESTURE_PINCH, GESTURE_POINT}:
            self.last_motion_gesture = secondary_gesture
            self.last_motion_time = now
            self.recent_motion_gestures.append((now, secondary_gesture))
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
    recent_anchors: BoundedHistory[float | tuple[float, float]] = field(
        default_factory=lambda: BoundedHistory[float | tuple[float, float]](8)
    )

    def reset_tracking(self) -> None:
        self.anchor = None
        self.position_source = "none"
        self.recent_anchors.clear()
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
        self.recent_anchors.append(current_anchor)
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
