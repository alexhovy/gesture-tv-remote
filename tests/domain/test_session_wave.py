import unittest

from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_MIC,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
)
from src.domain.session import GestureSession
from tests.helpers.config_helpers import app_config
from tests.helpers.session_helpers import hand_state


class SessionWaveTests(unittest.TestCase):
    def test_two_fingers_then_open_emits_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._two_fingers(session, now=0.1)
        self._two_fingers(session, now=0.2)
        self._two_fingers(session, now=0.3)
        decision = self._open(session, 0.50, now=0.4)

        self.assertEqual(decision.command_gesture, GESTURE_BACK)
        self.assertIn("two_finger_back=BACK", decision.debug_message)

    def test_single_two_finger_misread_does_not_emit_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._two_fingers(session, now=0.1)
        decision = self._open(session, 0.50, now=0.2)

        self.assertIsNone(decision.command_gesture)

    def test_sustained_two_fingers_emits_mic(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._two_fingers(session, now=0.1)
        self._two_fingers(session, now=0.2)
        self._two_fingers(session, now=0.3)
        mic = self._two_fingers(session, now=1.1)
        open_palm = self._open(session, 0.50, now=1.2)

        self.assertEqual(mic.command_gesture, GESTURE_MIC)
        self.assertIn("two_finger_back=MIC", mic.debug_message)
        self.assertIsNone(open_palm.command_gesture)

    def test_unknown_between_two_fingers_resets_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.52, now=0.0)
        self._two_fingers(session, now=0.1)
        self._two_fingers(session, now=0.2)
        session.evaluate(
            [hand_state(None, center=(0.50, 0.50), size=0.20)],
            now=0.3,
        )
        decision = self._open(session, 0.50, now=0.4)

        self.assertIsNone(decision.command_gesture)

    def test_slow_drift_without_reversal_does_not_emit_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._open(session, 0.56, now=0.2)
        self._open(session, 0.62, now=0.4)
        decision = self._open(session, 0.72, now=0.6)

        self.assertIsNone(decision.command_gesture)
        self.assertIn("two_finger_back_state=armed=False", decision.debug_message)

    def test_vertical_open_palm_movement_does_not_emit_back(self) -> None:
        session = GestureSession(app_config())
        session.evaluate(
            [
                hand_state(GESTURE_OPEN_PALM, center=(0.50, 0.50), size=0.20),
                hand_state(GESTURE_OPEN_PALM, center=(0.80, 0.50), size=0.20),
            ],
            now=0.0,
        )
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.35, 0.70), size=0.20)],
            now=0.1,
        )
        decision = session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.62, 0.40), size=0.20)],
            now=0.2,
        )

        self.assertIsNone(decision.command_gesture)
        self.assertIn("two_finger_back_state=armed=False", decision.debug_message)

    def test_point_pinch_and_fist_do_not_emit_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)

        point = session.evaluate(
            [hand_state(GESTURE_POINT, center=(0.35, 0.50), size=0.20)],
            now=0.1,
        )
        pinch = session.evaluate(
            [hand_state(GESTURE_PINCH, center=(0.62, 0.50), size=0.20)],
            now=0.2,
        )
        fist = session.evaluate(
            [hand_state(GESTURE_FIST, center=(0.35, 0.50), size=0.20)],
            now=0.3,
        )

        self.assertNotEqual(point.command_gesture, GESTURE_BACK)
        self.assertNotEqual(pinch.command_gesture, GESTURE_BACK)
        self.assertNotEqual(fist.command_gesture, GESTURE_BACK)

    def test_two_finger_back_does_not_repeat_while_open_palm_is_held(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._open(session, 0.50, now=0.0)
        self._two_fingers(session, now=0.1)
        self._two_fingers(session, now=0.2)
        self._two_fingers(session, now=0.3)
        first = self._open(session, 0.50, now=0.4)
        blocked = self._open(session, 0.50, now=0.5)
        self._two_fingers(session, now=1.2)
        self._two_fingers(session, now=1.3)
        self._two_fingers(session, now=1.4)
        second = self._open(session, 0.50, now=1.5)

        self.assertEqual(first.command_gesture, GESTURE_BACK)
        self.assertIsNone(blocked.command_gesture)
        self.assertEqual(second.command_gesture, GESTURE_BACK)

    def _open(self, session: GestureSession, x: float, now: float):
        hands = [hand_state(GESTURE_OPEN_PALM, center=(x, 0.50), size=0.20)]
        if now == 0.0:
            hands.append(hand_state(GESTURE_OPEN_PALM, center=(0.80, 0.50), size=0.20))
        return session.evaluate(hands, now=now)

    def _two_fingers(self, session: GestureSession, now: float):
        return session.evaluate(
            [hand_state(GESTURE_TWO_FINGERS, center=(0.50, 0.50), size=0.20)],
            now=now,
        )


if __name__ == "__main__":
    unittest.main()
