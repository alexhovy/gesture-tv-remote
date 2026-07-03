from dataclasses import dataclass

from src.domain.geometry.display_geometry import DisplayMotionScale
from src.domain.gestures.motion_filter import classify_volume_joystick
from src.domain.gestures.motion_gesture import MotionJoystickState
from src.shared.config import AppConfig


@dataclass(frozen=True)
class VolumeEvaluation:
    command_gesture: str | None
    position: tuple[float, float] | None
    distance: float


def evaluate_volume_motion(
    volume: MotionJoystickState,
    active_center: tuple[float, float],
    active_size: float,
    config: AppConfig,
    now: float,
    motion_scale: DisplayMotionScale | None = None,
) -> VolumeEvaluation:
    motion_scale = motion_scale or DisplayMotionScale()
    if not isinstance(volume.anchor, float):
        volume.anchor = active_center[1]
        volume.visual_anchor = active_center

    distance = scaled_distance(
        active_size,
        config.gesture.volume_distance_ratio,
        config.gesture.volume_min_distance,
        config.gesture.volume_max_distance,
    )
    decision = classify_volume_joystick(
        volume.anchor if isinstance(volume.anchor, float) else None,
        active_center[1],
        distance,
        motion_scale,
    )
    volume.motion_scale_x = motion_scale.x
    volume.motion_scale_y = motion_scale.y
    volume.record_decision(decision)
    return VolumeEvaluation(
        command_gesture=volume.command(
            decision,
            active_center[1],
            now,
            config.gesture.debounce_seconds,
        ),
        position=active_center,
        distance=distance,
    )


def scaled_distance(
    hand_size: float,
    ratio: float,
    min_distance: float,
    max_distance: float,
) -> float:
    if hand_size <= 0:
        return min_distance

    return min(max(hand_size * ratio, min_distance), max_distance)
