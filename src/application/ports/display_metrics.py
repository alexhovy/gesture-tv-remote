from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DisplaySize:
    width: float
    height: float


class DisplayMetricsPort(Protocol):
    def latest_size(self) -> DisplaySize | None: ...
