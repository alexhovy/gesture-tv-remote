from collections import deque
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class BoundedHistory(Generic[T]):
    max_length: int
    _values: deque[T] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_length <= 0:
            raise ValueError("max_length must be greater than zero")
        self._values = deque(maxlen=self.max_length)

    def append(self, value: T) -> None:
        self._values.append(value)

    def clear(self) -> None:
        self._values.clear()

    def latest(self) -> T | None:
        if not self._values:
            return None
        return self._values[-1]

    def values(self) -> tuple[T, ...]:
        return tuple(self._values)

    def __len__(self) -> int:
        return len(self._values)
