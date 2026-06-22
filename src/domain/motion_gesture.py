from dataclasses import dataclass, field

from src.domain.constants import DEBUG_UNKNOWN, GESTURE_BACK, GESTURE_PINCH, GESTURE_POINT
from src.domain.gesture_history import BoundedHistory
from src.domain.motion_filter import JoystickDecision
from src.domain.session_types import HandState


@dataclass
class MotionGestureInterpreter:
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

    def effective_motion_gesture(self, gesture: str | None, now: float) -> str | None:
        if gesture in {GESTURE_PINCH, GESTURE_POINT}:
            self.last_motion_gesture = gesture
            self.last_motion_time = now
            self.recent_motion_gestures.append((now, gesture))
            return gesture

        if gesture is not None and self._last_motion_within_grace(now):
            return self.last_motion_gesture

        return None

    def _last_motion_within_grace(self, now: float) -> bool:
        return (
            self.last_motion_gesture is not None
            and self.last_motion_time is not None
            and now - self.last_motion_time <= self.motion_grace_seconds
        )

    def missing_within_grace(self, now: float) -> bool:
        return (
            self.last_seen_time is not None
            and now - self.last_seen_time <= self.motion_grace_seconds
        )

    def zoom_freeze_reason(self, active_hand: HandState | None, now: float) -> str:
        if active_hand is not None:
            return "active_hand_present"
        if self.missing_within_grace(now):
            return "active_hand_grace"
        return "none"


@dataclass
class MotionJoystickState:
    anchor: float | tuple[float, float] | None = None
    active_gesture: str | None = None
    armed: bool = True
    neutral_frames: int = 0
    last_emit_time: float | None = None
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
        self.last_emit_time = None
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
        now: float,
        repeat_seconds: float,
    ) -> str | None:
        self.recent_anchors.append(current_anchor)
        if decision.in_neutral:
            self.neutral_frames += 1
            self.active_gesture = None
            self.armed = True
            self.last_emit_time = None
            self.phase = "armed"
            self.last_blocked_reason = "rearmed"
            return None

        self.neutral_frames = 0
        if decision.gesture is None:
            self.phase = "armed" if self.armed else "triggered"
            self.last_blocked_reason = decision.blocked_reason
            return None

        if self.armed:
            self.active_gesture = decision.gesture
            self.armed = False
            self.last_emit_time = now
            self.phase = "triggered"
            return decision.gesture

        self.phase = "triggered"
        if decision.gesture != self.active_gesture:
            self.last_blocked_reason = "awaiting_neutral"
            return None

        if (
            self.last_emit_time is not None
            and now - self.last_emit_time >= repeat_seconds
        ):
            self.last_emit_time = now
            self.last_blocked_reason = "repeat"
            return decision.gesture

        self.last_blocked_reason = "holding"
        return None


@dataclass
class WaveGestureState:
    min_horizontal_distance: float = 0.20
    max_vertical_distance: float = 0.12
    max_window_seconds: float = 0.8
    min_direction_distance: float = 0.06
    positions: BoundedHistory[tuple[float, tuple[float, float]]] = field(
        default_factory=lambda: BoundedHistory[tuple[float, tuple[float, float]]](12)
    )
    armed: bool = True
    last_emit_time: float | None = None
    last_blocked_reason: str | None = None

    def reset(self) -> None:
        self.positions.clear()
        self.armed = True
        self.last_emit_time = None
        self.last_blocked_reason = None

    def reset_for_pose_change(self) -> None:
        self.positions.clear()
        self.armed = True
        self.last_blocked_reason = "pose_changed"

    def command(self, center: tuple[float, float], now: float, debounce_seconds: float) -> str | None:
        self.positions.append((now, center))
        recent = [
            (timestamp, position)
            for timestamp, position in self.positions.values()
            if now - timestamp <= self.max_window_seconds
        ]
        if len(recent) < 3:
            if not self.armed:
                self.armed = True
            self.last_blocked_reason = "collecting"
            return None

        xs = [position[0] for _, position in recent]
        ys = [position[1] for _, position in recent]
        horizontal_distance = max(xs) - min(xs)
        vertical_distance = max(ys) - min(ys)
        if not self.armed and horizontal_distance < self.min_direction_distance:
            self.armed = True
        if horizontal_distance < self.min_horizontal_distance:
            self.last_blocked_reason = "horizontal_too_small"
            return None
        if vertical_distance > self.max_vertical_distance:
            self.last_blocked_reason = "vertical_too_large"
            return None
        if not self._has_reversal(recent):
            self.last_blocked_reason = "no_reversal"
            return None
        if not self.armed:
            self.last_blocked_reason = "awaiting_reset"
            return None
        if self.last_emit_time is not None and now - self.last_emit_time < debounce_seconds:
            self.last_blocked_reason = "debounced"
            return None

        self.armed = False
        self.last_emit_time = now
        self.last_blocked_reason = "emitted"
        return GESTURE_BACK

    def _has_reversal(
        self,
        positions: list[tuple[float, tuple[float, float]]],
    ) -> bool:
        previous_direction = 0
        for (_, previous), (_, current) in zip(positions, positions[1:], strict=False):
            dx = current[0] - previous[0]
            if abs(dx) < self.min_direction_distance:
                continue
            direction = 1 if dx > 0 else -1
            if previous_direction and direction != previous_direction:
                return True
            previous_direction = direction
        return False
