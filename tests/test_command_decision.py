import unittest

from src.domain.command_decision import CommandDecision, EmitDebounce
from src.domain.constants import (
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
)


class CommandDecisionTests(unittest.TestCase):
    def test_open_fist_open_emits_select(self) -> None:
        decision = CommandDecision()

        self.assertIsNone(
            decision.evaluate(
                GESTURE_OPEN_PALM,
                GESTURE_FIST,
                now=0.0,
                fist_hold_home_seconds=0.7,
            )
        )

        self.assertEqual(
            decision.evaluate(
                GESTURE_FIST,
                GESTURE_OPEN_PALM,
                now=0.3,
                fist_hold_home_seconds=0.7,
            ),
            GESTURE_OPEN_TO_FIST,
        )

    def test_held_fist_emits_home(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            now=1.0,
            fist_hold_home_seconds=0.7,
        )

        self.assertEqual(
            decision.evaluate(
                GESTURE_FIST,
                GESTURE_FIST,
                now=1.7,
                fist_hold_home_seconds=0.7,
            ),
            GESTURE_HOME,
        )

    def test_home_does_not_repeat_until_fist_reopens(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            now=1.0,
            fist_hold_home_seconds=0.7,
        )
        decision.evaluate(
            GESTURE_FIST,
            GESTURE_FIST,
            now=1.7,
            fist_hold_home_seconds=0.7,
        )

        self.assertIsNone(
            decision.evaluate(
                GESTURE_FIST,
                GESTURE_FIST,
                now=2.5,
                fist_hold_home_seconds=0.7,
            )
        )
        self.assertIsNone(
            decision.evaluate(
                GESTURE_FIST,
                GESTURE_OPEN_PALM,
                now=2.6,
                fist_hold_home_seconds=0.7,
            )
        )


class EmitDebounceTests(unittest.TestCase):
    def test_same_gesture_is_suppressed_until_debounce_expires(self) -> None:
        debounce = EmitDebounce()

        self.assertTrue(debounce.should_emit("HOME", now=1.0, debounce_seconds=0.3))
        debounce.record_emit("HOME", now=1.0)
        self.assertFalse(debounce.should_emit("HOME", now=1.1, debounce_seconds=0.3))
        self.assertTrue(debounce.should_emit("HOME", now=1.31, debounce_seconds=0.3))


if __name__ == "__main__":
    unittest.main()
