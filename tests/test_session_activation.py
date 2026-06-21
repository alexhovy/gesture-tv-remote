import unittest

from src.domain.constants import (
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
)
from src.domain.session import GestureSession
from src.shared.config import AppConfig
from tests.session_helpers import hand_state


class SessionActivationTests(unittest.TestCase):
    def test_decision_is_not_activated_before_primary_open_palm(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [hand_state(GESTURE_POINT, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_decision_activates_from_primary_open_palm(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_decision_does_not_activate_from_non_upright_open_palm(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [
                hand_state(
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
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate(
            [
                hand_state(
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
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
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
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate([], now=0.36)

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_brief_primary_dropout_preserves_previous_gesture(self) -> None:
        session = GestureSession(AppConfig(primary_lost_grace_seconds=0.35))
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )
        session.evaluate([], now=0.1)
        session.evaluate(
            [hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)],
            now=0.2,
        )

        decision = session.evaluate(
            [hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)],
            now=0.6,
        )

        self.assertEqual(decision.command_gesture, GESTURE_OPEN_TO_FIST)

    def test_decision_reports_activation_alongside_command_gesture(self) -> None:
        session = GestureSession(AppConfig())

        decision = session.evaluate(
            [
                hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20),
                hand_state(GESTURE_TWO_FINGERS, center=(0.70, 0.50), size=0.20),
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
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = hand_state(GESTURE_TWO_FINGERS, center=(0.70, 0.50), size=0.20)

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertEqual(decision.zoom_landmarks, [primary.landmarks, secondary.landmarks])

    def test_secondary_hand_does_not_steal_primary_when_closer_to_anchor(self) -> None:
        session = GestureSession(AppConfig(primary_match_max_distance=0.35))
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.30, 0.50), size=0.20)],
            now=0.0,
        )
        secondary = hand_state(GESTURE_TWO_FINGERS, center=(0.31, 0.50), size=0.20)
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.36, 0.50), size=0.20)

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
            [hand_state(GESTURE_OPEN_PALM, center=(0.30, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate(
            [hand_state(GESTURE_TWO_FINGERS, center=(0.31, 0.50), size=0.20)],
            now=0.1,
        )

        self.assertTrue(decision.activated)
        self.assertTrue(decision.primary_temporarily_lost)
        self.assertEqual(decision.zoom_landmarks, [])

    def test_non_upright_secondary_hand_is_ignored(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = hand_state(
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
        self.assertIn("secondary_index=none", decision.debug_message)
        self.assertIn(
            "1:gesture=TWO_FINGERS:upright=False:upright_reason=tilted",
            decision.debug_message,
        )

    def test_upside_down_secondary_hand_is_ignored(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = hand_state(
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
        self.assertIn("secondary_index=none", decision.debug_message)
        self.assertIn(
            "1:gesture=TWO_FINGERS:upright=False:upright_reason=upside_down",
            decision.debug_message,
        )

    def test_unknown_secondary_hand_keeps_zoom_stable(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        secondary = hand_state(None, center=(0.70, 0.50), size=0.20)

        decision = session.evaluate([primary, secondary], now=0.0)

        self.assertTrue(decision.activated)
        self.assertEqual(decision.zoom_landmarks, [primary.landmarks, secondary.landmarks])
        self.assertTrue(decision.freeze_zoom)
        self.assertIn("zoom_freeze_reason=secondary_present", decision.debug_message)


if __name__ == "__main__":
    unittest.main()
