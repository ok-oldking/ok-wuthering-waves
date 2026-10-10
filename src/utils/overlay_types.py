"""Shared, Qt-free type aliases for the map-overlay-interaction feature.

This module intentionally has **no** dependency on PySide6/Qt, the game
runtime, OCR, or screen capture. It only provides lightweight structural
types that the pure-logic modules (``map_geometry``, ``PathRoute``,
``TargetTracker``, ``MapMarksDB`` and the draw-item builders) share.

Keeping these aliases in one Qt-free place lets the pure-logic layer be
imported and tested on a development machine (conda env ``wuwa`` / local
``.venv``) without pulling in Qt. The render layer is responsible for
converting these structural values into Qt objects (e.g. ``ColorTuple`` ->
``QColor``, ``Rect`` -> ``QRect``/``QRegion``).

Feature: map-overlay-interaction (Requirements 10.6)
"""

from __future__ import annotations

from typing import NamedTuple, Optional, Tuple

# An RGB color, components in the 0..255 range. The render layer converts this
# to a QColor; parsing (e.g. parse_section_color) stays Qt-free by returning
# this tuple. See design "PathRoute" / "parse_section_color".
ColorTuple = Tuple[int, int, int]

# Screen-space pixel point (integer coordinates), e.g. a projected icon center.
Point = Tuple[int, int]

# Game-unit coordinate point (float). location.x/y and Path_Node
# xposition/yposition share this coordinate system.
GamePoint = Tuple[float, float]


class Rect(NamedTuple):
    """An axis-aligned rectangle in screen pixels, given by its edges.

    Stored as inclusive-left/top, exclusive-right/bottom edges so that width
    and height are simply ``right - left`` and ``bottom - top``. This is the
    representation used for Hit_Box hit-testing (``point_in_rect``) and for
    composing the ``setMask`` ``QRegion`` in the interaction window.
    """

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


# A hit-box paired with its visual z-order, used by topmost_hit to resolve
# overlapping icons (higher z == visually on top). See Requirements 1.10, 2.8.
HitBoxWithZ = Tuple[Rect, int]

# Optional index into a collection (e.g. topmost_hit result, draw-item index).
Index = Optional[int]


__all__ = [
    "ColorTuple",
    "Point",
    "GamePoint",
    "Rect",
    "HitBoxWithZ",
    "Index",
]
