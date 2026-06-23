from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CropRect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class CroppedFrame:
    frame: Any
    crop: CropRect
