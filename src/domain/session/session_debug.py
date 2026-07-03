import math
from dataclasses import dataclass

from src.domain.constants import DEBUG_NONE, DEBUG_UNKNOWN
from src.domain.geometry.landmarks import hand_upright_metrics, hand_upright_reason
from src.domain.gestures.motion_gesture import MotionJoystickState
from src.domain.session.session_state import GestureSessionState
from src.domain.session.session_types import HandState, PointerDebug, VolumeDebug
from src.shared.config import AppConfig


@dataclass(frozen=True)
class SessionDebugSnapshot:
    hands: list[HandState]
    active_anchor: tuple[float, float] | None
    pointer: MotionJoystickState
    volume: MotionJoystickState
    upright_max_tilt_ratio: float
    pose_blocked_reason: str | None = None
    two_finger_back_armed: bool = False
    two_finger_back_frames: int = 0
    two_finger_back_required_frames: int = 0


def build_debug_snapshot(
    state: GestureSessionState,
    config: AppConfig,
    hand_states: list[HandState],
    active_anchor: tuple[float, float] | None,
) -> SessionDebugSnapshot:
    return SessionDebugSnapshot(
        hands=hand_states,
        active_anchor=active_anchor,
        pointer=state.pointer,
        volume=state.volume,
        upright_max_tilt_ratio=config.gesture.hand_upright_max_tilt_ratio,
        pose_blocked_reason=state.pose_blocked_reason,
        two_finger_back_armed=state.two_finger_back.armed,
        two_finger_back_frames=state.two_finger_back.two_finger_frames,
        two_finger_back_required_frames=state.two_finger_back.required_frames,
    )


@dataclass(frozen=True)
class ActiveDebugContext:
    active_index: int
    active_gesture: str | None
    effective_motion_gesture: str | None
    commandable_motion_gesture: str | None
    volume_gesture: str | None
    pointer_gesture: str | None
    two_finger_back_gesture: str | None
    active_size: float
    pointer_distance: float
    volume_distance: float
    command_gesture: str | None
    pointer_position: tuple[float, float] | None
    zoom_hands: int
    zoom_freeze_reason: str
    anchor_locked: bool


class SessionDebugRenderer:
    def render_inactive(
        self,
        snapshot: SessionDebugSnapshot,
        active_index: int | None = None,
    ) -> str:
        debug_index = "none" if active_index is None else str(active_index)
        return (
            f"hands={len(snapshot.hands)} activated=False "
            f"gestures={self._debug_gestures(snapshot.hands)} "
            f"need_upright_open_palm active_index={debug_index} zoom_hands=0 "
            f"{self._debug_hands(snapshot)}"
        )

    def render_temporarily_lost(
        self,
        snapshot: SessionDebugSnapshot,
        command_gesture: str | None,
        zoom_freeze_reason: str,
        anchor_locked: bool,
    ) -> str:
        return (
            f"hands={len(snapshot.hands)} activated=True "
            f"gestures={self._debug_gestures(snapshot.hands)} "
            f"active_hand_temporarily_lost "
            f"command={command_gesture or DEBUG_NONE} "
            f"active_index=none zoom_hands=0 "
            f"pointer_state={self.pointer_state(snapshot.pointer, None)} "
            f"volume_state={self.volume_state(snapshot.volume)} "
            f"zoom_freeze_reason={zoom_freeze_reason} "
            f"anchor_locked={anchor_locked} "
            f"{self._debug_hands(snapshot)}"
        )

    def render_active(
        self,
        snapshot: SessionDebugSnapshot,
        context: ActiveDebugContext,
    ) -> str:
        pointer_state = self.pointer_state(
            snapshot.pointer,
            context.pointer_position,
        )
        return (
            f"hands={len(snapshot.hands)} activated=True "
            f"gestures={self._debug_gestures(snapshot.hands)} "
            f"active={context.active_gesture or DEBUG_UNKNOWN} "
            f"effective_motion={context.effective_motion_gesture or DEBUG_NONE} "
            f"motion_command={context.commandable_motion_gesture or DEBUG_NONE} "
            f"pose_blocked={snapshot.pose_blocked_reason or DEBUG_NONE} "
            f"volume={context.volume_gesture or DEBUG_NONE} "
            f"pointer={context.pointer_gesture or DEBUG_NONE} "
            f"two_finger_back={context.two_finger_back_gesture or DEBUG_NONE} "
            f"two_finger_back_state={self._two_finger_back_state(snapshot)} "
            f"size={context.active_size:.2f} "
            f"pointer_distance={context.pointer_distance:.2f} "
            f"volume_distance={context.volume_distance:.2f} "
            f"command={context.command_gesture or DEBUG_NONE} "
            f"pointer_state={pointer_state} "
            f"volume_state={self.volume_state(snapshot.volume)} "
            f"active_index={context.active_index} "
            f"zoom_hands={context.zoom_hands} "
            f"zoom_freeze_reason={context.zoom_freeze_reason} "
            f"anchor_locked={context.anchor_locked} "
            f"{self._debug_hands(snapshot)}"
        )

    def pointer_debug(
        self,
        pointer: MotionJoystickState,
        current_position: tuple[float, float] | None,
    ) -> PointerDebug:
        anchor_position = pointer.anchor if isinstance(pointer.anchor, tuple) else None
        return PointerDebug(
            anchor=anchor_position,
            current=current_position,
            active_gesture=pointer.active_gesture,
            candidate_gesture=pointer.candidate_gesture,
            phase=pointer.phase,
            armed=pointer.armed,
            activation_distance=pointer.activation_distance,
            neutral_distance=pointer.neutral_distance,
            threshold_ratio=pointer.threshold_ratio,
            in_neutral=pointer.in_neutral,
            blocked_reason=pointer.last_blocked_reason,
            motion_scale_x=pointer.motion_scale_x,
            motion_scale_y=pointer.motion_scale_y,
        )

    def volume_debug(
        self,
        volume: MotionJoystickState,
        current_position: tuple[float, float] | None,
    ) -> VolumeDebug:
        anchor_y = volume.anchor if isinstance(volume.anchor, float) else None
        return VolumeDebug(
            anchor=volume.visual_anchor if anchor_y is not None else None,
            anchor_y=anchor_y,
            current=current_position,
            active_gesture=volume.active_gesture,
            candidate_gesture=volume.candidate_gesture,
            phase=volume.phase,
            armed=volume.armed,
            activation_distance=volume.activation_distance,
            neutral_distance=volume.neutral_distance,
            threshold_ratio=volume.threshold_ratio,
            in_neutral=volume.in_neutral,
            blocked_reason=volume.last_blocked_reason,
            motion_scale_x=volume.motion_scale_x,
            motion_scale_y=volume.motion_scale_y,
        )

    def pointer_state(
        self,
        pointer: MotionJoystickState,
        current_position: tuple[float, float] | None,
    ) -> str:
        anchor_position = pointer.anchor if isinstance(pointer.anchor, tuple) else None
        anchor = self._debug_position(anchor_position)
        current = self._debug_position(current_position)
        dx, dy = self._debug_delta(anchor_position, current_position)
        return (
            f"anchor={anchor}:active={pointer.active_gesture or DEBUG_NONE}"
            f":phase={pointer.phase}"
            f":armed={pointer.armed}"
            f":neutral_frames={pointer.neutral_frames}"
            f":source={pointer.position_source}"
            f":current={current}:dx={dx}:dy={dy}"
            f":candidate={pointer.candidate_gesture or DEBUG_NONE}"
            f":magnitude={pointer.candidate_magnitude:.3f}"
            f":activation={pointer.activation_distance:.3f}"
            f":neutral={pointer.neutral_distance:.3f}"
            f":threshold_ratio={pointer.threshold_ratio:.2f}"
            f":in_neutral={pointer.in_neutral}"
            f":blocked={pointer.last_blocked_reason or DEBUG_NONE}"
        )

    def volume_state(self, volume: MotionJoystickState) -> str:
        anchor_y = volume.anchor if isinstance(volume.anchor, float) else None
        anchor = DEBUG_NONE if anchor_y is None else f"{anchor_y:.2f}"
        return (
            f"anchor={anchor}:active={volume.active_gesture or DEBUG_NONE}"
            f":phase={volume.phase}"
            f":armed={volume.armed}"
            f":neutral_frames={volume.neutral_frames}"
            f":candidate={volume.candidate_gesture or DEBUG_NONE}"
            f":magnitude={volume.candidate_magnitude:.3f}"
            f":activation={volume.activation_distance:.3f}"
            f":neutral={volume.neutral_distance:.3f}"
            f":threshold_ratio={volume.threshold_ratio:.2f}"
            f":in_neutral={volume.in_neutral}"
            f":blocked={volume.last_blocked_reason or DEBUG_NONE}"
        )

    def _debug_hands(self, snapshot: SessionDebugSnapshot) -> str:
        if not snapshot.hands:
            return "hand_details=[]"

        details = [
            self._debug_hand(index, hand, snapshot)
            for index, hand in enumerate(snapshot.hands)
        ]
        return f"hand_details=[{';'.join(details)}]"

    def _debug_hand(
        self,
        index: int,
        hand: HandState,
        snapshot: SessionDebugSnapshot,
    ) -> str:
        center_x, center_y = hand.center
        distance = "none"
        if snapshot.active_anchor is not None:
            distance_value = math.hypot(
                center_x - snapshot.active_anchor[0],
                center_y - snapshot.active_anchor[1],
            )
            distance = f"{distance_value:.2f}"
        dx, dy, tilt_ratio = hand_upright_metrics(hand.landmarks)
        tilt = "inf" if math.isinf(tilt_ratio) else f"{tilt_ratio:.2f}"
        reason = hand_upright_reason(
            hand.landmarks,
            snapshot.upright_max_tilt_ratio,
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
            f":active_dist={distance}"
        )

    @staticmethod
    def _debug_gestures(hands: list[HandState]) -> list[str]:
        return [hand.gesture or DEBUG_UNKNOWN for hand in hands]

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

    @staticmethod
    def _two_finger_back_state(snapshot: SessionDebugSnapshot) -> str:
        return (
            f"armed={snapshot.two_finger_back_armed}"
            f":frames={snapshot.two_finger_back_frames}"
            f":required={snapshot.two_finger_back_required_frames}"
        )
