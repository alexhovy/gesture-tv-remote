from dataclasses import dataclass

from src.domain.commands.command_decision import (
    CommandDecision,
    EmitDebounce,
    TwoFingerBackDecision,
)
from src.domain.gestures.activation_tracker import ActiveHandTracker
from src.domain.gestures.motion_gesture import (
    MotionGestureInterpreter,
    MotionJoystickState,
)


@dataclass
class GestureSessionState:
    active: ActiveHandTracker
    motion: MotionGestureInterpreter
    command_decision: CommandDecision
    two_finger_back: TwoFingerBackDecision
    emit: EmitDebounce
    volume: MotionJoystickState
    pointer: MotionJoystickState
    pose_blocked_reason: str | None = None

    @classmethod
    def create(cls, motion_grace_seconds: float) -> "GestureSessionState":
        return cls(
            active=ActiveHandTracker(),
            motion=MotionGestureInterpreter(motion_grace_seconds=motion_grace_seconds),
            command_decision=CommandDecision(),
            two_finger_back=TwoFingerBackDecision(),
            emit=EmitDebounce(),
            volume=MotionJoystickState(),
            pointer=MotionJoystickState(),
        )

    def reset_activation(self) -> None:
        self.active.reset()
        self.motion.reset()
        self.emit.record_idle()
        self.command_decision.reset()
        self.two_finger_back.reset()
        self.reset_motion_tracking()
        self.pose_blocked_reason = None

    def reset_for_handoff(self) -> None:
        self.active.reset()
        self.motion.reset()
        self.command_decision.reset()
        self.two_finger_back.reset()
        self.reset_motion_tracking()
        self.pose_blocked_reason = None

    def reset_motion_tracking(self) -> None:
        self.volume.reset_tracking()
        self.pointer.reset_tracking()

    def reset_motion_diagnostics(self) -> None:
        self.pointer.last_blocked_reason = None
        self.volume.last_blocked_reason = None
        self.pointer.reset_diagnostics()
        self.volume.reset_diagnostics()

    def motion_anchor_locked(self) -> bool:
        return self.pointer.anchor is not None or self.volume.anchor is not None

    def mark_motion_grace(self, reason: str) -> None:
        if self.pointer.anchor is not None:
            self.pointer.last_blocked_reason = reason
        if self.volume.anchor is not None:
            self.volume.last_blocked_reason = reason
