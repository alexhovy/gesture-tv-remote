import cv2

from src.domain.landmarks import HAND_CONNECTIONS
from src.domain.session_types import PointerDebug
from src.infrastructure.camera.video_preprocessing import CropRect


COLOR_ACTIVE = (0, 165, 255)
COLOR_ARMED = (0, 220, 0)
COLOR_BLOCKED = (0, 0, 255)
COLOR_CURRENT = (255, 255, 255)
COLOR_DIRECTION = (255, 180, 0)
COLOR_NEUTRAL = (160, 160, 160)
COLOR_RELEASE = (0, 255, 255)


def draw_simple_landmarks(frame, landmarks) -> None:
    height, width = frame.shape[:2]

    for start, end in HAND_CONNECTIONS:
        start_point = (int(landmarks[start].x * width), int(landmarks[start].y * height))
        end_point = (int(landmarks[end].x * width), int(landmarks[end].y * height))
        cv2.line(frame, start_point, end_point, (0, 255, 0), 2)

    for landmark in landmarks:
        point = (int(landmark.x * width), int(landmark.y * height))
        cv2.circle(frame, point, 4, (0, 0, 255), -1)


def draw_pointer_zones(
    frame,
    pointer: PointerDebug | None,
    display_crop: CropRect,
) -> None:
    if pointer is None or pointer.anchor is None:
        return

    height, width = frame.shape[:2]
    anchor = _point_to_pixels(pointer.anchor, display_crop, width, height)
    current = (
        _point_to_pixels(pointer.current, display_crop, width, height)
        if pointer.current is not None
        else None
    )

    release_radius = _distance_to_pixels(
        pointer.release_distance,
        display_crop,
        width,
        height,
    )
    neutral_radius = _distance_to_pixels(
        pointer.neutral_distance,
        display_crop,
        width,
        height,
    )
    activation_x = _x_distance_to_pixels(pointer.activation_distance, display_crop, width)
    activation_y = _y_distance_to_pixels(pointer.activation_distance, display_crop, height)
    color = _state_color(pointer)

    if release_radius > 0:
        cv2.circle(frame, anchor, release_radius, COLOR_RELEASE, 2)
    if neutral_radius > 0:
        cv2.circle(frame, anchor, neutral_radius, COLOR_NEUTRAL, 1)

    left_x = anchor[0] - activation_x
    right_x = anchor[0] + activation_x
    up_y = anchor[1] - activation_y
    down_y = anchor[1] + activation_y
    cv2.line(frame, (left_x, 0), (left_x, height), COLOR_DIRECTION, 1)
    cv2.line(frame, (right_x, 0), (right_x, height), COLOR_DIRECTION, 1)
    cv2.line(frame, (0, up_y), (width, up_y), COLOR_DIRECTION, 1)
    cv2.line(frame, (0, down_y), (width, down_y), COLOR_DIRECTION, 1)

    cv2.line(frame, (0, anchor[1]), (width, anchor[1]), COLOR_NEUTRAL, 1)
    cv2.line(frame, (anchor[0], 0), (anchor[0], height), COLOR_NEUTRAL, 1)
    cv2.circle(frame, anchor, 5, color, -1)

    if current is not None:
        cv2.line(frame, anchor, current, color, 2)
        cv2.circle(frame, current, 6, COLOR_CURRENT, 2)

    _draw_pointer_labels(frame, anchor, activation_x, activation_y, width, height, pointer)


def _draw_pointer_labels(
    frame,
    anchor: tuple[int, int],
    activation_x: int,
    activation_y: int,
    width: int,
    height: int,
    pointer: PointerDebug,
) -> None:
    put_text = getattr(cv2, "putText", None)
    if put_text is None:
        return

    font = getattr(cv2, "FONT_HERSHEY_SIMPLEX", 0)
    label_color = _state_color(pointer)
    labels = [
        ("LEFT", (max(4, anchor[0] - activation_x - 54), anchor[1] - 8)),
        ("RIGHT", (min(width - 72, anchor[0] + activation_x + 8), anchor[1] - 8)),
        ("UP", (anchor[0] + 8, max(16, anchor[1] - activation_y - 8))),
        ("DOWN", (anchor[0] + 8, min(height - 8, anchor[1] + activation_y + 18))),
    ]
    for text, position in labels:
        put_text(frame, text, position, font, 0.45, COLOR_DIRECTION, 1)

    state = pointer.active_gesture or pointer.candidate_gesture or pointer.phase
    put_text(
        frame,
        f"{state} {pointer.blocked_reason or ''}".strip(),
        (8, max(18, height - 12)),
        font,
        0.5,
        label_color,
        1,
    )


def _state_color(pointer: PointerDebug) -> tuple[int, int, int]:
    if pointer.active_gesture is not None:
        return COLOR_ACTIVE
    if pointer.blocked_reason in {"settling_release", "rearmed"}:
        return COLOR_RELEASE
    if pointer.blocked_reason is not None:
        return COLOR_BLOCKED
    if pointer.armed:
        return COLOR_ARMED
    return COLOR_NEUTRAL


def _point_to_pixels(
    point: tuple[float, float],
    crop: CropRect,
    width: int,
    height: int,
) -> tuple[int, int]:
    x, y = point
    return (
        int(round((x - crop.x) / crop.width * width)),
        int(round((y - crop.y) / crop.height * height)),
    )


def _distance_to_pixels(
    distance: float,
    crop: CropRect,
    width: int,
    height: int,
) -> int:
    return max(
        0,
        min(
            _x_distance_to_pixels(distance, crop, width),
            _y_distance_to_pixels(distance, crop, height),
        ),
    )


def _x_distance_to_pixels(distance: float, crop: CropRect, width: int) -> int:
    if crop.width <= 0:
        return 0
    return max(0, int(round(distance / crop.width * width)))


def _y_distance_to_pixels(distance: float, crop: CropRect, height: int) -> int:
    if crop.height <= 0:
        return 0
    return max(0, int(round(distance / crop.height * height)))
