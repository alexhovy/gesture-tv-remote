import unittest
from types import SimpleNamespace

from src.domain.constants import (
    GESTURE_OPEN_PALM,
    GESTURE_FIST,
    GESTURE_MIC,
    GESTURE_OPEN_TO_FIST,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_POINT_RIGHT,
    GESTURE_TWO_FINGERS,
    GESTURE_VOLUME_DOWN,
)
from src.domain.landmarks import (
    LANDMARK_COUNT,
    LANDMARK_INDEX_TIP,
    LANDMARK_MIDDLE_MCP,
    LANDMARK_WRIST,
)
from src.domain.session import GestureSession, HandState
from src.shared.config import AppConfig


class GestureSessionTests(unittest.TestCase):
    def test_decision_is_not_activated_before_primary_open_palm(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [_hand_state(GESTURE_POINT, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_decision_activates_from_primary_open_palm(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_decision_does_not_activate_from_non_upright_open_palm(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [
                _hand_state(
                    GESTURE_OPEN_PALM,
                    center=(0.20, 0.50),
                    size=0.20,
                    upright=False,
                )
            ],
            now=0.0,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_active_session_deactivates_when_primary_is_not_upright(self) -> None:
        session = GestureSession(AppConfig())
        session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate(
            [
                _hand_state(
                    None,
                    center=(0.20, 0.50),
                    size=0.20,
                    upright=False,
                )
            ],
            now=0.1,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_active_session_stays_active_during_brief_primary_dropout(self) -> None:
        session = GestureSession(AppConfig(primary_lost_grace_seconds=0.35))
        session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate([], now=0.2)

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self.assertTrue(decision.primary_temporarily_lost)
        self.assertIn("primary_temporarily_lost", decision.debug_message)

    def test_active_session_deactivates_after_primary_dropout_grace(self) -> None:
        session = GestureSession(AppConfig(primary_lost_grace_seconds=0.35))
        session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate([], now=0.36)

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_brief_primary_dropout_preserves_previous_gesture(self) -> None:
        session = GestureSession(AppConfig(primary_lost_grace_seconds=0.35))
        session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )
        session.evaluate([], now=0.1)
        session.evaluate(
            [_hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)],
            now=0.2,
        )

        decision = session.evaluate(
            [_hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)],
            now=0.6,
        )

        self.assertEqual(decision.command_gesture, GESTURE_OPEN_TO_FIST)

    def test_decision_reports_activation_alongside_command_gesture(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [
                _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20),
                _hand_state(GESTURE_TWO_FINGERS, center=(0.70, 0.50), size=0.20),
            ],
            now=0.0,
        )

        self.assertTrue(decision.activated)
        self.assertIsNotNone(decision.command_gesture)
        self.assertIn("primary_index=0 secondary_index=1", decision.debug_message)
        self.assertIn("zoom_hands=2", decision.debug_message)
        self.assertIn(
            "0:gesture=OPEN_PALM:upright=True",
            decision.debug_message,
        )
        self.assertIn(
            ":center=(0.20,0.50):size=0.20",
            decision.debug_message,
        )
        self.assertIn(
            "1:gesture=TWO_FINGERS:upright=True",
            decision.debug_message,
        )
        self.assertIn(
            ":center=(0.70,0.50):size=0.20",
            decision.debug_message,
        )

    def test_zoom_landmarks_include_valid_primary_and_secondary_hands(self) -> None:
        session = GestureSession(AppConfig())
        primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = _hand_state(GESTURE_TWO_FINGERS, center=(0.70, 0.50), size=0.20)

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertEqual(decision.zoom_landmarks, [primary.landmarks, secondary.landmarks])

    def test_secondary_hand_does_not_steal_primary_when_closer_to_anchor(self) -> None:
        session = GestureSession(AppConfig(primary_match_max_distance=0.35))
        session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.30, 0.50), size=0.20)],
            now=0.0,
        )
        secondary = _hand_state(GESTURE_TWO_FINGERS, center=(0.31, 0.50), size=0.20)
        primary = _hand_state(GESTURE_OPEN_PALM, center=(0.36, 0.50), size=0.20)

        decision = session.evaluate([secondary, primary], now=0.1)

        self.assertTrue(decision.activated)
        self.assertIn("primary=OPEN_PALM secondary=TWO_FINGERS", decision.debug_message)
        self.assertEqual(decision.zoom_landmarks, [primary.landmarks, secondary.landmarks])

    def test_secondary_gesture_is_not_promoted_to_missing_primary(self) -> None:
        session = GestureSession(
            AppConfig(
                primary_lost_grace_seconds=0.35,
                primary_match_max_distance=0.35,
            )
        )
        session.evaluate(
            [_hand_state(GESTURE_OPEN_PALM, center=(0.30, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate(
            [_hand_state(GESTURE_TWO_FINGERS, center=(0.31, 0.50), size=0.20)],
            now=0.1,
        )

        self.assertTrue(decision.activated)
        self.assertTrue(decision.primary_temporarily_lost)
        self.assertEqual(decision.zoom_landmarks, [])

    def test_non_upright_secondary_hand_is_ignored(self) -> None:
        session = GestureSession(AppConfig())
        primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = _hand_state(
            GESTURE_TWO_FINGERS,
            center=(0.70, 0.50),
            size=0.20,
            upright=False,
            upright_vector=(0.30, -0.10),
        )

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self.assertEqual(decision.zoom_landmarks, [primary.landmarks])

    def test_loose_secondary_upright_gate_allows_tilted_secondary_hand(self) -> None:
        session = GestureSession(
            AppConfig(secondary_hand_upright_max_tilt_ratio=2.0)
        )
        primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = _hand_state(
            GESTURE_TWO_FINGERS,
            center=(0.70, 0.50),
            size=0.20,
            upright=False,
            upright_vector=(0.16, -0.10),
        )

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertTrue(decision.activated)
        self.assertEqual(decision.command_gesture, GESTURE_MIC)
        self.assertEqual(decision.zoom_landmarks, [primary.landmarks, secondary.landmarks])
        self.assertIn("secondary=TWO_FINGERS", decision.debug_message)

    def test_secondary_upright_gate_rejects_upside_down_secondary_hand(self) -> None:
        session = GestureSession(
            AppConfig(secondary_hand_upright_max_tilt_ratio=2.0)
        )
        primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = _hand_state(
            GESTURE_TWO_FINGERS,
            center=(0.70, 0.50),
            size=0.20,
            upright=False,
            upright_vector=(0.00, 0.10),
        )

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self.assertEqual(decision.zoom_landmarks, [primary.landmarks])

    def test_unknown_secondary_hand_is_ignored_for_zoom(self) -> None:
        session = GestureSession(AppConfig())
        primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = _hand_state(None, center=(0.70, 0.50), size=0.20)

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertTrue(decision.activated)
        self.assertEqual(decision.zoom_landmarks, [primary.landmarks])

    def test_pointer_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            _evaluate_pointer_move(hand_size=0.10, start_x=0.50, end_x=0.55),
            GESTURE_POINT_RIGHT,
        )
        self.assertIsNone(
            _evaluate_pointer_move(hand_size=0.25, start_x=0.50, end_x=0.55)
        )

    def test_volume_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            _evaluate_volume_move(hand_size=0.10, start_y=0.50, end_y=0.54),
            GESTURE_VOLUME_DOWN,
        )
        self.assertIsNone(
            _evaluate_volume_move(hand_size=0.25, start_y=0.50, end_y=0.54)
        )

    def test_scaled_distance_clamps_to_minimum_and_maximum(self) -> None:
        self.assertEqual(
            GestureSession._scaled_distance(
                hand_size=0.01,
                ratio=0.45,
                min_distance=0.04,
                max_distance=0.14,
            ),
            0.04,
        )
        self.assertEqual(
            GestureSession._scaled_distance(
                hand_size=1.00,
                ratio=0.45,
                min_distance=0.04,
                max_distance=0.14,
            ),
            0.14,
        )


def _evaluate_pointer_move(hand_size: float, start_x: float, end_x: float) -> str | None:
    session = GestureSession(AppConfig())
    primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

    session.evaluate(
        [
            primary,
            _hand_state(
                GESTURE_POINT,
                center=(0.70, 0.50),
                size=hand_size,
                index_position=(start_x, 0.50),
            ),
        ],
        now=0.0,
    )
    return session.evaluate(
        [
            primary,
            _hand_state(
                GESTURE_POINT,
                center=(0.70, 0.50),
                size=hand_size,
                index_position=(end_x, 0.50),
            ),
        ],
        now=0.1,
    ).command_gesture


def _evaluate_volume_move(hand_size: float, start_y: float, end_y: float) -> str | None:
    session = GestureSession(AppConfig())
    primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

    session.evaluate(
        [
            primary,
            _hand_state(GESTURE_PINCH, center=(0.70, start_y), size=hand_size),
        ],
        now=0.0,
    )
    return session.evaluate(
        [
            primary,
            _hand_state(GESTURE_PINCH, center=(0.70, end_y), size=hand_size),
        ],
        now=0.1,
    ).command_gesture


def _hand_state(
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


if __name__ == "__main__":
    unittest.main()
