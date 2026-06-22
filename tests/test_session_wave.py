import unittest

from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
)
from src.domain.session import GestureSession
from tests.config_helpers import app_config
from tests.session_helpers import hand_state


class SessionWaveTests(unittest.TestCase):
    def test_open_palm_left_right_wave_emits_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._open(session, 0.35, now=0.1)
        decision = self._open(session, 0.62, now=0.2)

        self.assertEqual(decision.command_gesture, GESTURE_BACK)
        self.assertIn("wave=BACK", decision.debug_message)

    def test_open_palm_right_left_wave_emits_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._open(session, 0.65, now=0.1)
        decision = self._open(session, 0.38, now=0.2)

        self.assertEqual(decision.command_gesture, GESTURE_BACK)

    def test_slow_drift_without_reversal_does_not_emit_back(self) -> None:
        session = GestureSession(app_config())
        self._open(session, 0.50, now=0.0)
        self._open(session, 0.56, now=0.2)
        self._open(session, 0.62, now=0.4)
        decision = self._open(session, 0.72, now=0.6)

        self.assertIsNone(decision.command_gesture)
        self.assertIn("blocked=no_reversal", decision.debug_message)

    def test_vertical_open_palm_movement_does_not_emit_back(self) -> None:
        session = GestureSession(app_config())
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.50, 0.50), size=0.20)],
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
        self.assertIn("blocked=vertical_too_large", decision.debug_message)

    def test_point_pinch_and_fist_do_not_emit_wave_back(self) -> None:
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

    def test_wave_back_does_not_repeat_until_open_palm_settles(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._open(session, 0.50, now=0.0)
        self._open(session, 0.35, now=0.1)
        first = self._open(session, 0.62, now=0.2)
        blocked = self._open(session, 0.35, now=0.3)
        self._open(session, 0.50, now=1.2)
        self._open(session, 0.50, now=1.3)
        self._open(session, 0.35, now=1.4)
        second = self._open(session, 0.62, now=1.5)

        self.assertEqual(first.command_gesture, GESTURE_BACK)
        self.assertIsNone(blocked.command_gesture)
        self.assertIn("blocked=awaiting_reset", blocked.debug_message)
        self.assertEqual(second.command_gesture, GESTURE_BACK)

    def _open(self, session: GestureSession, x: float, now: float):
        return session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(x, 0.50), size=0.20)],
            now=now,
        )


if __name__ == "__main__":
    unittest.main()
