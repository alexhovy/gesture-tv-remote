import unittest

from src.domain.commands.command_decision import (
    CommandDecision,
    EmitDebounce,
    TwoFingerBackDecision,
)
from src.domain.constants import (
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_MIC,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
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

    def test_unknown_between_open_and_fist_still_emits_select(self) -> None:
        decision = CommandDecision()

        self.assertIsNone(
            decision.evaluate(
                None,
                GESTURE_OPEN_PALM,
                now=0.0,
                fist_hold_home_seconds=0.7,
            )
        )
        self.assertIsNone(
            decision.evaluate(
                GESTURE_OPEN_PALM,
                None,
                now=0.1,
                fist_hold_home_seconds=0.7,
            )
        )
        self.assertIsNone(
            decision.evaluate(
                None,
                GESTURE_FIST,
                now=0.2,
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

    def test_unknown_between_fist_and_open_still_emits_select(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            now=0.1,
            fist_hold_home_seconds=0.7,
        )
        self.assertIsNone(
            decision.evaluate(
                GESTURE_FIST,
                None,
                now=0.2,
                fist_hold_home_seconds=0.7,
            )
        )

        self.assertEqual(
            decision.evaluate(
                None,
                GESTURE_OPEN_PALM,
                now=0.3,
                fist_hold_home_seconds=0.7,
            ),
            GESTURE_OPEN_TO_FIST,
        )

    def test_fist_unknown_grace_expires_before_select(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            now=0.1,
            fist_hold_home_seconds=0.7,
        )
        decision.evaluate(
            GESTURE_FIST,
            None,
            now=0.2,
            fist_hold_home_seconds=0.7,
        )
        decision.evaluate(
            None,
            None,
            now=0.3,
            fist_hold_home_seconds=0.7,
        )
        decision.evaluate(
            None,
            None,
            now=0.4,
            fist_hold_home_seconds=0.7,
        )

        self.assertIsNone(
            decision.evaluate(
                None,
                GESTURE_OPEN_PALM,
                now=0.5,
                fist_hold_home_seconds=0.7,
            )
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

    def test_home_does_not_emit_after_active_unknown_grace_expires(self) -> None:
        decision = CommandDecision()
        decision.evaluate(
            GESTURE_OPEN_PALM,
            GESTURE_FIST,
            now=1.0,
            fist_hold_home_seconds=0.7,
        )
        decision.evaluate(
            GESTURE_FIST,
            None,
            now=1.1,
            fist_hold_home_seconds=0.7,
        )
        decision.evaluate(
            None,
            None,
            now=1.2,
            fist_hold_home_seconds=0.7,
        )

        self.assertIsNone(
            decision.evaluate(
                None,
                None,
                now=1.7,
                fist_hold_home_seconds=0.7,
            )
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


class TwoFingerBackDecisionTests(unittest.TestCase):
    def test_three_two_finger_frames_then_open_emits_back(self) -> None:
        decision = TwoFingerBackDecision()

        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.0))
        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.1))
        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.2))

        self.assertEqual(
            decision.evaluate(GESTURE_OPEN_PALM, now=0.3),
            GESTURE_BACK,
        )

    def test_single_two_finger_frame_does_not_emit_back(self) -> None:
        decision = TwoFingerBackDecision()

        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.0))

        self.assertIsNone(decision.evaluate(GESTURE_OPEN_PALM, now=0.1))

    def test_other_gesture_resets_armed_back(self) -> None:
        decision = TwoFingerBackDecision()
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.0)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.1)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.2)

        self.assertIsNone(decision.evaluate(GESTURE_POINT, now=0.3))
        self.assertIsNone(decision.evaluate(GESTURE_OPEN_PALM, now=0.4))

    def test_single_unknown_frame_does_not_reset_two_finger_back(self) -> None:
        decision = TwoFingerBackDecision()
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.0)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.1)
        self.assertIsNone(decision.evaluate(None, now=0.2))
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.3)

        self.assertEqual(
            decision.evaluate(GESTURE_OPEN_PALM, now=0.4),
            GESTURE_BACK,
        )

    def test_second_unknown_frame_resets_two_finger_back(self) -> None:
        decision = TwoFingerBackDecision()
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.0)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.1)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.2)
        self.assertIsNone(decision.evaluate(None, now=0.3))
        self.assertIsNone(decision.evaluate(None, now=0.4))

        self.assertIsNone(decision.evaluate(GESTURE_OPEN_PALM, now=0.5))

    def test_sustained_two_fingers_emits_mic_once(self) -> None:
        decision = TwoFingerBackDecision()

        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.0))
        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.1))
        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=0.2))
        self.assertEqual(
            decision.evaluate(GESTURE_TWO_FINGERS, now=1.0),
            GESTURE_MIC,
        )
        self.assertIsNone(decision.evaluate(GESTURE_TWO_FINGERS, now=1.1))
        self.assertIsNone(decision.evaluate(GESTURE_OPEN_PALM, now=1.2))

    def test_mic_suppresses_select_after_two_finger_hold(self) -> None:
        decision = TwoFingerBackDecision(select_suppression_seconds=0.5)

        decision.evaluate(GESTURE_TWO_FINGERS, now=0.0)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.1)
        decision.evaluate(GESTURE_TWO_FINGERS, now=0.2)

        self.assertEqual(
            decision.evaluate(GESTURE_TWO_FINGERS, now=1.0),
            GESTURE_MIC,
        )
        decision.evaluate(GESTURE_OPEN_PALM, now=1.1)
        self.assertTrue(decision.should_suppress_select(now=1.4))
        self.assertFalse(decision.should_suppress_select(now=1.6))


if __name__ == "__main__":
    unittest.main()
