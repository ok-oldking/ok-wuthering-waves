from __future__ import annotations

from dataclasses import dataclass

from .interfaces import Box


@dataclass(frozen=True)
class RelBox:
    """Relative box coordinates in [0,1] for the full frame."""

    x1: float
    y1: float
    x2: float
    y2: float

    def normalized(self) -> "RelBox":
        left = min(self.x1, self.x2)
        right = max(self.x1, self.x2)
        top = min(self.y1, self.y2)
        bottom = max(self.y1, self.y2)
        return RelBox(left, top, right, bottom)


def pixel_box_to_rel(box: Box, frame_width: int, frame_height: int) -> RelBox:
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame_width/frame_height must be > 0")
    b = box.normalized()
    return RelBox(
        x1=b.x1 / frame_width,
        y1=b.y1 / frame_height,
        x2=b.x2 / frame_width,
        y2=b.y2 / frame_height,
    )


def rel_box_to_pixel(box: RelBox, frame_width: int, frame_height: int) -> Box:
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame_width/frame_height must be > 0")
    b = box.normalized()
    return Box(
        int(round(b.x1 * frame_width)),
        int(round(b.y1 * frame_height)),
        int(round(b.x2 * frame_width)),
        int(round(b.y2 * frame_height)),
    )

