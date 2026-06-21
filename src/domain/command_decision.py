from dataclasses import dataclass

from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
)


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
