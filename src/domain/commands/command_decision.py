from dataclasses import dataclass

from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_MIC,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_TWO_FINGERS,
)


@dataclass
class CommandDecision:
    fist_started_at: float | None = None
    home_emitted_for_fist: bool = False
    unknown_grace_frames: int = 2
    unknown_frames: int = 0
    last_definitive_gesture: str | None = None

    def reset(self) -> None:
        self.fist_started_at = None
        self.home_emitted_for_fist = False
        self.unknown_frames = 0
        self.last_definitive_gesture = None

    def evaluate(
        self,
        previous_gesture: str | None,
        gesture: str | None,
        now: float,
        fist_hold_home_seconds: float,
    ) -> str | None:
        effective_previous = previous_gesture
        if gesture is None:
            self.unknown_frames += 1
        else:
            if (
                previous_gesture is None
                and self.unknown_frames <= self.unknown_grace_frames
            ):
                effective_previous = self.last_definitive_gesture
            self.unknown_frames = 0

        if effective_previous == GESTURE_OPEN_PALM and gesture == GESTURE_FIST:
            self.fist_started_at = now
            self.home_emitted_for_fist = False

        current_or_missing_fist = (
            gesture == GESTURE_FIST
            or (gesture is None and previous_gesture == GESTURE_FIST)
            or (
                gesture is None
                and self.last_definitive_gesture == GESTURE_FIST
                and self.unknown_frames <= self.unknown_grace_frames
            )
        )
        if current_or_missing_fist and self.fist_started_at is not None:
            if (
                not self.home_emitted_for_fist
                and now - self.fist_started_at >= fist_hold_home_seconds
            ):
                self.home_emitted_for_fist = True
                return GESTURE_HOME

        command_gesture = None
        if effective_previous == GESTURE_FIST and gesture == GESTURE_OPEN_PALM:
            should_select = (
                self.fist_started_at is not None and not self.home_emitted_for_fist
            )
            self.reset()
            if should_select:
                command_gesture = GESTURE_OPEN_TO_FIST

        if (
            command_gesture is None
            and gesture not in {GESTURE_FIST, None}
            and effective_previous != GESTURE_FIST
        ):
            self.reset()

        if gesture is not None:
            self.last_definitive_gesture = gesture

        return command_gesture


@dataclass
class TwoFingerBackDecision:
    required_frames: int = 3
    mic_hold_seconds: float = 1.0
    unknown_grace_frames: int = 1
    two_finger_frames: int = 0
    unknown_frames: int = 0
    started_at: float | None = None
    armed: bool = False
    mic_emitted: bool = False

    def reset(self) -> None:
        self.two_finger_frames = 0
        self.unknown_frames = 0
        self.started_at = None
        self.armed = False
        self.mic_emitted = False

    def evaluate(self, gesture: str | None, now: float) -> str | None:
        if gesture == GESTURE_TWO_FINGERS:
            self.unknown_frames = 0
            if self.two_finger_frames == 0:
                self.started_at = now
            self.two_finger_frames += 1
            if self.two_finger_frames >= self.required_frames:
                self.armed = True
            if (
                self.armed
                and not self.mic_emitted
                and self.started_at is not None
                and now - self.started_at >= self.mic_hold_seconds
            ):
                self.mic_emitted = True
                return GESTURE_MIC
            return None

        if gesture is None and (self.two_finger_frames > 0 or self.armed):
            self.unknown_frames += 1
            if self.unknown_frames <= self.unknown_grace_frames:
                return None

        if gesture == GESTURE_OPEN_PALM and self.armed and not self.mic_emitted:
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
