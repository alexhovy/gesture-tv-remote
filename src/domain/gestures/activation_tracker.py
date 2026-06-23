import math
from dataclasses import dataclass

from src.domain.constants import GESTURE_OPEN_PALM
from src.domain.session.session_types import HandState
from src.shared.config import AppConfig


@dataclass
class ActiveHandTracker:
    position: tuple[float, float] | None = None
    last_seen_time: float | None = None
    previous_gesture: str | None = None

    def reset(self) -> None:
        self.position = None
        self.last_seen_time = None
        self.previous_gesture = None

    def update_seen(self, hand: HandState, now: float) -> None:
        self.position = hand.center
        self.last_seen_time = now

    def missing_within_grace(self, config: AppConfig, now: float) -> bool:
        if self.position is None or self.last_seen_time is None:
            return False
        grace_seconds = max(0.0, config.gesture.active_hand_lost_grace_seconds)
        return now - self.last_seen_time <= grace_seconds

    def find_active_index(
        self, hands: list[HandState], config: AppConfig
    ) -> int | None:
        if not hands:
            return None
        if self.position is None:
            return next(
                (
                    index
                    for index, hand in enumerate(hands)
                    if hand.upright and hand.gesture == GESTURE_OPEN_PALM
                ),
                None,
            )

        max_distance = max(0.0, config.gesture.active_hand_match_max_distance)
        candidates = [
            index
            for index, hand in enumerate(hands)
            if self.distance_from_active(hand) <= max_distance
        ]
        if not candidates:
            return None

        upright_candidates = [index for index in candidates if hands[index].upright]
        if not upright_candidates:
            return min(
                candidates, key=lambda index: self.distance_from_active(hands[index])
            )

        if self.previous_gesture is None:
            return min(
                upright_candidates,
                key=lambda index: self.distance_from_active(hands[index]),
            )

        same_gesture = [
            index
            for index in upright_candidates
            if hands[index].gesture == self.previous_gesture
        ]
        if same_gesture:
            return min(
                same_gesture, key=lambda index: self.distance_from_active(hands[index])
            )

        return min(
            upright_candidates,
            key=lambda index: self.distance_from_active(hands[index]),
        )

    def distance_from_active(self, hand: HandState) -> float:
        if self.position is None:
            return math.inf
        target_x, target_y = self.position
        return math.hypot(hand.center[0] - target_x, hand.center[1] - target_y)
