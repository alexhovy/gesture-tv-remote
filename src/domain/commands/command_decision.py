from dataclasses import dataclass

from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_TWO_FINGERS,
)


@dataclass
class CommandDecision:
    fist_started_at: float | None = None
    home_emitted_for_fist: bool = False

    def reset(self) -> None:
        self.fist_started_at = None
        self.home_emitted_for_fist = False

    def evaluate(
        self,
        previous_gesture: str | None,
        gesture: str | None,
        now: float,
        fist_hold_home_seconds: float,
    ) -> str | None:
        if previous_gesture == GESTURE_OPEN_PALM and gesture == GESTURE_FIST:
            self.fist_started_at = now
            self.home_emitted_for_fist = False

        current_or_missing_fist = gesture == GESTURE_FIST or (
            gesture is None and previous_gesture == GESTURE_FIST
        )
        if current_or_missing_fist and self.fist_started_at is not None:
            if (
                not self.home_emitted_for_fist
                and now - self.fist_started_at >= fist_hold_home_seconds
            ):
                self.home_emitted_for_fist = True
                return GESTURE_HOME

        if previous_gesture == GESTURE_FIST and gesture == GESTURE_OPEN_PALM:
            should_select = (
                self.fist_started_at is not None and not self.home_emitted_for_fist
            )
            self.reset()
            if should_select:
                return GESTURE_OPEN_TO_FIST

        if gesture not in {GESTURE_FIST, None} and previous_gesture != GESTURE_FIST:
            self.reset()

        return None


@dataclass
class TwoFingerBackDecision:
    required_frames: int = 3
    two_finger_frames: int = 0
    armed: bool = False

    def reset(self) -> None:
        self.two_finger_frames = 0
        self.armed = False

    def evaluate(self, gesture: str | None) -> str | None:
        if gesture == GESTURE_TWO_FINGERS:
            self.two_finger_frames += 1
            if self.two_finger_frames >= self.required_frames:
                self.armed = True
            return None

        if gesture == GESTURE_OPEN_PALM and self.armed:
            self.reset()
            return GESTURE_BACK

        self.reset()
        return None


@dataclass
class EmitDebounce:
    last_command_time: float = 0.0
    last_command_gesture: str | None = None

    def should_emit(
        self, command_gesture: str, now: float, debounce_seconds: float
    ) -> bool:
        if command_gesture != self.last_command_gesture:
            return True
        return now - self.last_command_time >= debounce_seconds

    def record_emit(self, command_gesture: str, now: float) -> None:
        self.last_command_time = now
        self.last_command_gesture = command_gesture

    def record_idle(self) -> None:
        self.last_command_gesture = None
