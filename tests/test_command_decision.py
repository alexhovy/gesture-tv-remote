import unittest

from src.domain.command_decision import CommandDecision, EmitDebounce
from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
)


class CommandDecisionTests(unittest.TestCase):
    def test_primary_close_emits_select_after_chord_window(self) -> None:
        decision = CommandDecision()

        self.assertIsNone(
            decision.evaluate(
                GESTURE_OPEN_PALM,
                GESTURE_FIST,
                None,
                None,
                now=0.0,
                home_chord_seconds=0.35,
            )
        )

        self.assertEqual(
            decision.evaluate(
                GESTURE_FIST,
                GESTURE_FIST,
                None,
                None,
                now=0.36,
                home_chord_seconds=0.35,
            ),
            GESTURE_OPEN_TO_FIST,
        )

    def test_secondary_close_emits_back_after_chord_window(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            None,
            None,
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            now=0.0,
            home_chord_seconds=0.35,
        )

        self.assertEqual(
            decision.evaluate(
                None,
                None,
                GESTURE_FIST,
                GESTURE_FIST,
                now=0.36,
                home_chord_seconds=0.35,
            ),
            GESTURE_BACK,
        )

    def test_two_close_transitions_emit_home_inside_chord_window(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            None,
            None,
            now=1.0,
            home_chord_seconds=0.35,
        )

        self.assertEqual(
            decision.evaluate(
                GESTURE_FIST,
                GESTURE_FIST,
                GESTURE_OPEN_PALM,
                GESTURE_FIST,
                now=1.2,
                home_chord_seconds=0.35,
            ),
            GESTURE_HOME,
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
