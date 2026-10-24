"""Pure geometry helpers for the map-overlay-interaction feature.

Every function in this module is a **side-effect-free pure function** and does
**not** import Qt (PySide6), the game runtime, OCR, or screen capture. This lets
the geometry layer be imported and tested on a development machine (conda env
``wuwa`` / local ``.venv``) without pulling in Qt.

The functions here cover:

- Game-unit <-> screen-pixel projection (``project_game_to_screen`` /
  ``project_screen_to_game``). The projection convention matches the existing
  ``MapItemOverlay.project_to_minimap``: ``sx = center_x + (gx - player_x) * scale``.
- Hit-box construction and point-in-rect testing for click hit-testing
  (``make_hitbox`` / ``point_in_rect``).
- Top-most overlapping hit resolution (``topmost_hit``).
- Compass bearing and minimap edge-arrow placement (``bearing_degrees`` /
  ``edge_arrow_position``).
- Euclidean distance in game units (``distance_game_units``).

Feature: map-overlay-interaction
Requirements: 1.4, 1.5, 1.6, 1.10, 2.8, 8.1, 8.2, 9.10
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple

from src.utils.overlay_types import HitBoxWithZ, Index, Point, Rect

__all__ = [
    "project_game_to_screen",
    "project_screen_to_game",
    "make_hitbox",
    "point_in_rect",
    "topmost_hit",
    "bearing_degrees",
    "edge_arrow_position",
    "distance_game_units",
]


def project_game_to_screen(
    gx: float,
    gy: float,
    player_x: float,
    player_y: float,
    scale: float,
    center_x: float,
    center_y: float,
) -> Point:
    """Project a game-unit coordinate to a screen-pixel point.

    Uses the same convention as ``MapItemOverlay.project_to_minimap``::

        sx = center_x + (gx - player_x) * scale
        sy = center_y + (gy - player_y) * scale

    The result components are truncated to ``int`` (matching the existing
    projection helper which returns ``int(px), int(py)``).

    Requirements: 1.10, 9.10
    """
    sx = center_x + (gx - player_x) * scale
    sy = center_y + (gy - player_y) * scale
    return int(sx), int(sy)


def project_screen_to_game(
    sx: float,
    sy: float,
    player_x: float,
    player_y: float,
    scale: float,
    center_x: float,
    center_y: float,
) -> Tuple[float, float]:
    """Inverse of :func:`project_game_to_screen` (requires ``scale > 0``).

    Solving ``sx = center_x + (gx - player_x) * scale`` for ``gx`` gives::

        gx = player_x + (sx - center_x) / scale
        gy = player_y + (sy - center_y) / scale

    Returns game-unit floats (no truncation).

    Requirements: 1.10, 9.10
    """
    if scale == 0:
        raise ValueError("scale must be non-zero to invert the projection")
    gx = player_x + (sx - center_x) / scale
    gy = player_y + (sy - center_y) / scale
    return float(gx), float(gy)


def make_hitbox(cx: int, cy: int, icon_size: int, expand: int) -> Rect:
    """Build a Hit_Box rectangle for an icon centered at ``(cx, cy)``.

    The icon display bounds are the ``icon_size`` x ``icon_size`` square
    centered on ``(cx, cy)`` using the same anchoring as the renderer
    (``half = icon_size // 2``; the pixmap is drawn at ``cx - half`` /
    ``cy - half``). Each edge is then expanded **outward** by exactly
    ``expand`` pixels.

    ``expand`` is expected to be in ``[0, 8]`` (the Hit_Box definition in the
    requirements); values are clamped to that range so the hit-box is never
    smaller than the icon and never larger than the outward upper bound.

    Requirements: 1.4
    """
    expand = max(0, min(8, int(expand)))
    half = int(icon_size) // 2
    icon_left = int(cx) - half
    icon_top = int(cy) - half
    icon_right = icon_left + int(icon_size)
    icon_bottom = icon_top + int(icon_size)
    return Rect(
        left=icon_left - expand,
        top=icon_top - expand,
        right=icon_right + expand,
        bottom=icon_bottom + expand,
    )


def point_in_rect(px: float, py: float, rect: Rect) -> bool:
    """Return ``True`` when ``(px, py)`` lies within ``rect``.

    ``Rect`` uses inclusive left/top, exclusive right/bottom edges (see
    ``overlay_types.Rect``), so the test is ``left <= px < right`` and
    ``top <= py < bottom``.

    Requirements: 1.5, 1.6
    """
    return rect.left <= px < rect.right and rect.top <= py < rect.bottom


def topmost_hit(px: float, py: float, hitboxes_with_z: Sequence[HitBoxWithZ]) -> Index:
    """Return the index of the visually top-most Hit_Box containing the point.

    Among all hit-boxes that contain ``(px, py)``, returns the index of the one
    with the largest ``z`` (visually on top). When several share the same
    maximal ``z``, the lowest index wins, making the result fully deterministic
    for a given input. Returns ``None`` when the point hits no Hit_Box.

    Requirements: 1.5, 1.6, 1.10, 2.8
    """
    best_index: Index = None
    best_z = None
    for index, (rect, z) in enumerate(hitboxes_with_z):
        if not point_in_rect(px, py, rect):
            continue
        if best_z is None or z > best_z:
            best_z = z
            best_index = index
    return best_index


def bearing_degrees(
    player_x: float,
    player_y: float,
    target_x: float,
    target_y: float,
) -> float:
    """Compass bearing from the player to the target, in ``[0, 360)``.

    Bearing follows screen-space compass convention:

    - ``0``   -> target is straight up (north, ``-y``)
    - ``90``  -> target is to the right (east, ``+x``)
    - ``180`` -> target is straight down (south, ``+y``)
    - ``270`` -> target is to the left (west, ``-x``)

    By convention, when player and target coincide the bearing is ``0``.

    Requirements: 8.1, 8.2
    """
    dx = target_x - player_x
    dy = target_y - player_y
    if dx == 0 and dy == 0:
        return 0.0
    # atan2(dx, -dy): up (-dy) maps to 0 deg, right (+dx) maps to 90 deg.
    deg = math.degrees(math.atan2(dx, -dy)) % 360.0
    # Floating-point rounding can push a tiny negative angle up to exactly
    # 360.0 after the modulo; wrap it back to 0.0 to keep the result in [0, 360).
    if deg >= 360.0:
        deg = 0.0
    return deg


def edge_arrow_position(bearing_deg: float, minimap_box) -> Point:
    """Point on the edge of ``minimap_box`` in the direction of ``bearing_deg``.

    Casts a ray from the minimap center along the compass ``bearing_deg`` (see
    :func:`bearing_degrees`) and returns the intersection with the box edge.
    ``minimap_box`` must expose ``x``, ``y``, ``width`` and ``height``
    attributes (same shape used by ``MapItemOverlay.build_draw_items``).

    Requirements: 8.1
    """
    cx = minimap_box.x + minimap_box.width / 2.0
    cy = minimap_box.y + minimap_box.height / 2.0
    half_w = minimap_box.width / 2.0
    half_h = minimap_box.height / 2.0

    rad = math.radians(bearing_deg % 360.0)
    # Direction vector matching bearing convention: 0 -> up, 90 -> right.
    dir_x = math.sin(rad)
    dir_y = -math.cos(rad)

    t_x = half_w / abs(dir_x) if abs(dir_x) > 1e-12 else math.inf
    t_y = half_h / abs(dir_y) if abs(dir_y) > 1e-12 else math.inf
    t = min(t_x, t_y)

    ex = cx + dir_x * t
    ey = cy + dir_y * t
    return int(ex), int(ey)


def distance_game_units(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance between two points in game units.

    Requirements: 9.10
    """
    return math.hypot(ax - bx, ay - by)
