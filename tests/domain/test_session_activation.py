import unittest

from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
)
from src.domain.session import GestureSession
from tests.helpers.config_helpers import app_config
from tests.helpers.session_helpers import hand_state


class SessionActivationTests(unittest.TestCase):
    def test_decision_is_not_activated_before_upright_open_palm(self) -> None:
        session = GestureSession(app_config())

        decision = session.evaluate(
            [hand_state(GESTURE_POINT, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_decision_activates_from_upright_open_palm(self) -> None:
        session = GestureSession(app_config())

        decision = session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self.assertIn("active_index=0", decision.debug_message)

    def test_open_fist_open_selects(self) -> None:
        session = GestureSession(app_config())
        open_hand = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        fist = hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)

        session.evaluate([open_hand], now=0.0)
        pending = session.evaluate([fist], now=0.1)
        decision = session.evaluate([open_hand], now=0.2)

        self.assertIsNone(pending.command_gesture)
        self.assertEqual(decision.command_gesture, GESTURE_OPEN_TO_FIST)
        self.assertIn("active=OPEN_PALM", decision.debug_message)

    def test_held_fist_emits_home(self) -> None:
        session = GestureSession(app_config(fist_hold_home_seconds=0.5))
        open_hand = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        fist = hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)

        session.evaluate([open_hand], now=0.0)
        session.evaluate([fist], now=0.1)
        decision = session.evaluate([fist], now=0.6)

        self.assertEqual(decision.command_gesture, GESTURE_HOME)

    def test_two_fingers_then_open_emits_back(self) -> None:
        session = GestureSession(app_config())
        open_hand = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)
        two_fingers = hand_state(GESTURE_TWO_FINGERS, center=(0.20, 0.50), size=0.20)

        session.evaluate([open_hand], now=0.0)
        session.evaluate([two_fingers], now=0.1)
        session.evaluate([two_fingers], now=0.2)
        session.evaluate([two_fingers], now=0.3)
        decision = session.evaluate([open_hand], now=0.4)

        self.assertTrue(decision.activated)
        self.assertEqual(decision.command_gesture, GESTURE_BACK)
        self.assertIn("two_finger_back=BACK", decision.debug_message)

    def test_decision_does_not_activate_from_non_upright_open_palm(self) -> None:
        session = GestureSession(app_config())

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

    def test_active_session_deactivates_when_active_hand_is_not_upright(self) -> None:
        session = GestureSession(app_config())
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

    def test_active_session_stays_active_during_brief_hand_dropout(self) -> None:
        session = GestureSession(app_config(active_hand_lost_grace_seconds=0.35))
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate([], now=0.2)

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self.assertTrue(decision.active_temporarily_lost)
        self.assertIn("active_hand_temporarily_lost", decision.debug_message)

    def test_active_session_deactivates_after_dropout_grace(self) -> None:
        session = GestureSession(app_config(active_hand_lost_grace_seconds=0.35))
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        decision = session.evaluate([], now=0.36)

        self.assertFalse(decision.activated)
        self.assertIsNone(decision.command_gesture)

    def test_home_can_emit_during_active_hand_dropout_grace(self) -> None:
        session = GestureSession(
            app_config(
                active_hand_lost_grace_seconds=0.80,
                fist_hold_home_seconds=0.50,
            )
        )
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )
        session.evaluate(
            [hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)],
            now=0.1,
        )

        decision = session.evaluate([], now=0.6)

        self.assertTrue(decision.active_temporarily_lost)
        self.assertEqual(decision.command_gesture, GESTURE_HOME)
        self.assertTrue(decision.freeze_zoom)
        self.assertFalse(decision.anchor_locked)
        self.assertIn("zoom_freeze_reason=command_pose", decision.debug_message)

    def test_fist_does_not_contribute_to_zoom(self) -> None:
        session = GestureSession(app_config(active_hand_lost_grace_seconds=0.80))
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)],
            now=0.0,
        )

        fist = session.evaluate(
            [hand_state(GESTURE_FIST, center=(0.20, 0.50), size=0.20)],
            now=0.1,
        )
        missing = session.evaluate([], now=0.2)

        self.assertTrue(fist.freeze_zoom)
        self.assertEqual(fist.zoom_landmarks, [])
        self.assertIn("zoom_hands=0", fist.debug_message)
        self.assertIn("zoom_freeze_reason=command_pose", fist.debug_message)
        self.assertTrue(missing.freeze_zoom)
        self.assertFalse(missing.anchor_locked)
        self.assertIn("zoom_freeze_reason=command_pose", missing.debug_message)

    def test_extra_hands_do_not_contribute_to_zoom_or_commands(self) -> None:
        session = GestureSession(app_config(active_hand_match_max_distance=0.35))
        active = hand_state(GESTURE_OPEN_PALM, center=(0.30, 0.50), size=0.20)
        extra = hand_state(GESTURE_TWO_FINGERS, center=(0.80, 0.50), size=0.20)

        decision = session.evaluate([active, extra], now=0.0)

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self._assert_zoom_bounds(decision.zoom_landmarks[0], (0.20, 0.40), (0.40, 0.60))
        self.assertIn("active_index=0", decision.debug_message)
        self.assertIn("zoom_hands=1", decision.debug_message)

    def test_zoom_uses_active_hand_center_and_size_near_frame_edge(self) -> None:
        session = GestureSession(app_config())

        decision = session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.63, 0.84), size=0.13)],
            now=0.0,
        )

        self._assert_zoom_bounds(
            decision.zoom_landmarks[0], (0.565, 0.775), (0.695, 0.905)
        )

    def test_active_hand_is_matched_by_position_after_other_hand_enters_first(
        self,
    ) -> None:
        session = GestureSession(app_config(active_hand_match_max_distance=0.35))
        active = hand_state(GESTURE_OPEN_PALM, center=(0.30, 0.50), size=0.20)
        extra = hand_state(GESTURE_TWO_FINGERS, center=(0.80, 0.50), size=0.20)

        session.evaluate([active], now=0.0)
        decision = session.evaluate([extra, active], now=0.1)

        self.assertTrue(decision.activated)
        self.assertIsNone(decision.command_gesture)
        self._assert_zoom_bounds(decision.zoom_landmarks[0], (0.20, 0.40), (0.40, 0.60))
        self.assertIn("active_index=1", decision.debug_message)

    def _assert_zoom_bounds(
        self,
        landmarks,
        expected_min: tuple[float, float],
        expected_max: tuple[float, float],
    ) -> None:
        self.assertEqual(len(landmarks), 2)
        self.assertAlmostEqual(landmarks[0].x, expected_min[0])
        self.assertAlmostEqual(landmarks[0].y, expected_min[1])
        self.assertAlmostEqual(landmarks[1].x, expected_max[0])
        self.assertAlmostEqual(landmarks[1].y, expected_max[1])


if __name__ == "__main__":
    unittest.main()
