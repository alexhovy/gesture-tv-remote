from types import SimpleNamespace

from src.domain.constants import (
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
)
from src.domain.geometry.landmarks import (
    LANDMARK_COUNT,
    LANDMARK_INDEX_TIP,
    LANDMARK_MIDDLE_MCP,
    LANDMARK_WRIST,
)
from src.domain.session import GestureSession
from src.domain.session.session_types import HandState
from tests.config_helpers import app_config


def evaluate_pointer_move(hand_size: float, start_x: float, end_x: float) -> str | None:
    session = GestureSession(app_config())
    open_hand = hand_state(GESTURE_OPEN_PALM, center=(start_x, 0.50), size=hand_size)

    session.evaluate([open_hand], now=0.0)
    session.evaluate(
        [
            hand_state(
                GESTURE_POINT,
                center=(start_x, 0.50),
                size=hand_size,
                index_position=(start_x, 0.50),
            )
        ],
        now=0.1,
    )
    first = session.evaluate(
        [
            hand_state(
                GESTURE_POINT,
                center=(end_x, 0.50),
                size=hand_size,
                index_position=(end_x, 0.50),
            )
        ],
        now=0.2,
    ).command_gesture
    if first is not None:
        return first
    return session.evaluate(
        [
            hand_state(
                GESTURE_POINT,
                center=(end_x, 0.50),
                size=hand_size,
                index_position=(end_x, 0.50),
            )
        ],
        now=0.3,
    ).command_gesture


def evaluate_volume_move(hand_size: float, start_y: float, end_y: float) -> str | None:
    session = GestureSession(app_config())
    open_hand = hand_state(GESTURE_OPEN_PALM, center=(0.70, start_y), size=hand_size)

    session.evaluate([open_hand], now=0.0)
    session.evaluate(
        [hand_state(GESTURE_PINCH, center=(0.70, start_y), size=hand_size)],
        now=0.1,
    )
    first = session.evaluate(
        [hand_state(GESTURE_PINCH, center=(0.70, end_y), size=hand_size)],
        now=0.2,
    ).command_gesture
    if first is not None:
        return first
    return session.evaluate(
        [hand_state(GESTURE_PINCH, center=(0.70, end_y), size=hand_size)],
        now=0.3,
    ).command_gesture


def hand_state(
    gesture: str | None,
    center: tuple[float, float],
    size: float,
    index_position: tuple[float, float] = (0.0, 0.0),
    upright: bool = True,
    upright_vector: tuple[float, float] = (0.0, -1.0),
) -> HandState:
    landmarks = [SimpleNamespace(x=0.0, y=0.0) for _ in range(LANDMARK_COUNT)]
    landmarks[LANDMARK_INDEX_TIP] = SimpleNamespace(
        x=index_position[0],
        y=index_position[1],
    )
    landmarks[LANDMARK_WRIST] = SimpleNamespace(x=0.0, y=0.0)
    landmarks[LANDMARK_MIDDLE_MCP] = SimpleNamespace(
        x=upright_vector[0],
        y=upright_vector[1],
    )

    return HandState(
        landmarks=landmarks,
        gesture=gesture,
        center=center,
        size=size,
        upright=upright,
    )
