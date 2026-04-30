from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class Box:
    """Pixel-space box (x1,y1,x2,y2)."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> int:
        return abs(self.y2 - self.y1)

    def normalized(self) -> "Box":
        left = min(self.x1, self.x2)
        right = max(self.x1, self.x2)
        top = min(self.y1, self.y2)
        bottom = max(self.y1, self.y2)
        return Box(left, top, right, bottom)


@dataclass(frozen=True)
class OCRText:
    text: str
    box: Box
    confidence: float
    font_size: int


class OCRAdapter(Protocol):
    def recognize(self, image_path: str, region: Optional[Box] = None) -> List[OCRText]:
        """Execute OCR on image_path. If region is given, limit OCR to that region."""

