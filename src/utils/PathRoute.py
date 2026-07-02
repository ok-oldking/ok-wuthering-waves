"""Pure-logic parsing/validation for the fixed route file ``assets/path.json``.

This module is part of the *pure-logic layer* of the map-overlay-interaction
feature. It has **no** dependency on PySide6/Qt, the game runtime, OCR, or
screen capture, so it can be imported and tested on a development machine
(conda env ``wuwa`` / local ``.venv``) without pulling in Qt.

It parses the route JSON into the structured, frozen models ``PathNode`` /
``Section`` / ``PathRoute`` and resolves each section's ``sectionColor`` into a
Qt-free ``(r, g, b)`` :data:`~src.utils.overlay_types.ColorTuple`. The render
layer is responsible for converting those tuples into ``QColor`` objects.

Design references:
- design.md "Components and Interfaces" -> "PathRoute"
- Requirements 4.2 (load + parse), 4.4 (parse failure handling),
  5.4 (per-section color), 5.8 (missing/invalid color -> default).

Feature: map-overlay-interaction
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from src.utils.map_geometry import project_game_to_screen
from src.utils.overlay_types import ColorTuple, Point

# Predefined default section color used when a section's ``sectionColor`` is
# missing or invalid (Requirement 5.8). White, opaque RGB.
DEFAULT_SECTION_COLOR: ColorTuple = (255, 255, 255)

# Every route node is rendered with the same icon (``qzx_04.png``). Customizing
# the icon per node is explicitly out of scope (design "未来考虑"); the key here
# is the Qt-free icon identifier the render layer resolves to a pixmap.
# Requirement 5.2.
PATH_NODE_ICON_KEY: str = "qzx_04"


class PathParseError(Exception):
    """Raised when ``path.json`` cannot be loaded or parsed into a route.

    Covers: file not found / JSON parse failure (``load_path_route``), and
    missing ``stateId``, missing ``sectionList`` or no valid nodes
    (``parse_path_route``). See Requirement 4.4.
    """


@dataclass(frozen=True)
class PathNode:
    """A single route point inside a :class:`Section`'s ``positionList``.

    ``x`` / ``y`` are the game-unit coordinates taken from the JSON's
    ``xposition`` / ``yposition`` fields (same coordinate system as
    ``location.x/y``).
    """

    position_id: str
    position_name: str
    position_type: str
    x: float
    y: float


@dataclass(frozen=True)
class Section:
    """One ``data.sectionList`` entry: an id, a resolved color and its nodes."""

    section_id: int
    color: ColorTuple
    nodes: Tuple[PathNode, ...]


@dataclass(frozen=True)
class PathRoute:
    """A parsed route: the map ``state_id`` plus its ordered sections."""

    state_id: int
    sections: Tuple[Section, ...]


def parse_section_color(raw: Any, default: ColorTuple = DEFAULT_SECTION_COLOR) -> ColorTuple:
    """Parse a single section's ``sectionColor`` (e.g. ``'#F4AE5C'``).

    Returns the matching ``(r, g, b)`` tuple for a valid ``#RRGGBB`` (or
    ``#RGB``) hex string. When the input is missing (``None``), not a string,
    or otherwise invalid, returns ``default`` (Requirement 5.8).

    Note: the comma-separated ``data.sectionColor`` string at the route root is
    intentionally ignored; only each section's own ``sectionColor`` is used
    (Requirement 5.4 / design decision).
    """
    if not isinstance(raw, str):
        return default

    value = raw.strip()
    if not value.startswith("#"):
        return default

    hex_digits = value[1:]

    # Support the common #RRGGBB form and the shorthand #RGB form.
    if len(hex_digits) == 6:
        pass
    elif len(hex_digits) == 3:
        hex_digits = "".join(ch * 2 for ch in hex_digits)
    else:
        return default

    try:
        r = int(hex_digits[0:2], 16)
        g = int(hex_digits[2:4], 16)
        b = int(hex_digits[4:6], 16)
    except ValueError:
        return default

    return (r, g, b)


def _parse_node(raw: Any) -> Optional[PathNode]:
    """Build a :class:`PathNode` from one ``positionList`` entry.

    Returns ``None`` (the node is skipped) when the entry is not a dict or its
    coordinates are missing/non-numeric, so that malformed individual points do
    not abort parsing of an otherwise valid route.
    """
    if not isinstance(raw, dict):
        return None

    if "xposition" not in raw or "yposition" not in raw:
        return None

    try:
        x = float(raw["xposition"])
        y = float(raw["yposition"])
    except (TypeError, ValueError):
        return None

    position_id = raw.get("positionId")
    if position_id is None:
        return None

    return PathNode(
        position_id=str(position_id),
        position_name=str(raw.get("positionName") or ""),
        position_type=str(raw.get("positionType") or ""),
        x=x,
        y=y,
    )


def _parse_section(raw: Any) -> Optional[Section]:
    """Build a :class:`Section` from one ``sectionList`` entry.

    Returns ``None`` when the entry is not a dict or contains no valid nodes;
    such empty sections are dropped from the parsed route.
    """
    if not isinstance(raw, dict):
        return None

    nodes = tuple(
        node
        for node in (_parse_node(p) for p in raw.get("positionList") or [])
        if node is not None
    )
    if not nodes:
        return None

    try:
        section_id = int(raw.get("sectionId"))
    except (TypeError, ValueError):
        section_id = 0

    color = parse_section_color(raw.get("sectionColor"))

    return Section(section_id=section_id, color=color, nodes=nodes)


def parse_path_route(data: dict) -> PathRoute:
    """Parse an already-loaded route JSON dict into a :class:`PathRoute`.

    The relevant structure lives under ``data.data`` (mirroring the real
    ``assets/path.json``): ``data.stateId`` and
    ``data.sectionList[].{sectionId, sectionColor, positionList[...]}``.

    Raises :class:`PathParseError` when ``stateId`` is missing,
    ``sectionList`` is missing, or no valid nodes remain after parsing
    (Requirement 4.4).
    """
    if not isinstance(data, dict):
        raise PathParseError("route data is not a JSON object")

    payload = data.get("data")
    if not isinstance(payload, dict):
        raise PathParseError("route data missing 'data' object")

    if "stateId" not in payload or payload.get("stateId") is None:
        raise PathParseError("route data missing 'stateId'")
    try:
        state_id = int(payload["stateId"])
    except (TypeError, ValueError):
        raise PathParseError("route 'stateId' is not an integer")

    section_list = payload.get("sectionList")
    if not isinstance(section_list, list):
        raise PathParseError("route data missing 'sectionList'")

    sections = tuple(
        section
        for section in (_parse_section(s) for s in section_list)
        if section is not None
    )
    if not sections:
        raise PathParseError("route contains no valid nodes")

    return PathRoute(state_id=state_id, sections=sections)


def load_path_route(path: str) -> PathRoute:
    """Read ``path`` from disk and parse it into a :class:`PathRoute`.

    Raises :class:`PathParseError` on file-not-found, JSON decode failure, or
    any of the structural validation failures from :func:`parse_path_route`
    (Requirement 4.4).
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise PathParseError(f"route file not found: {path}") from exc
    except OSError as exc:
        raise PathParseError(f"could not read route file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PathParseError(f"could not parse route JSON: {path}") from exc

    return parse_path_route(data)


@dataclass(frozen=True)
class PathLayer:
    """A Qt-free render description for one :class:`Section`'s polyline.

    Mirrors the design's draw model ``{ color, points, node_ids }`` and adds the
    uniform node icon key. One :class:`PathLayer` is produced per Section.

    - ``color``: the section's resolved ``(r, g, b)`` color (Requirement 5.4).
    - ``points``: the projected **screen-pixel** points, one per node, in
      ``positionList`` order. The render layer connects consecutive points with
      arrowed segments pointing from the earlier node to the later one
      (Requirement 5.3); a single point draws only the node icon (Requirement
      5.7).
    - ``node_ids``: the ``position_id`` of each node, aligned with ``points``.
    - ``node_icon``: the uniform icon key for every node, always
      :data:`PATH_NODE_ICON_KEY` (Requirement 5.2).
    """

    color: ColorTuple
    points: Tuple[Point, ...]
    node_ids: Tuple[str, ...]
    node_icon: str = field(default=PATH_NODE_ICON_KEY)

    @property
    def segments(self) -> Tuple[Tuple[Point, Point], ...]:
        """Ordered connection segments as consecutive point pairs.

        Yields ``max(0, len(points) - 1)`` segments; the i-th segment connects
        ``points[i]`` to ``points[i + 1]`` (Requirements 5.3, 5.7).
        """
        return tuple(
            (self.points[i], self.points[i + 1])
            for i in range(len(self.points) - 1)
        )


def build_path_layers(
    route: PathRoute,
    context_state_id: int,
    player_x: float,
    player_y: float,
    scale: float,
    center_x: float,
    center_y: float,
) -> Tuple[PathLayer, ...]:
    """Build one :class:`PathLayer` per Section from a parsed route.

    Each node's game-unit coordinate is projected to screen pixels via
    :func:`~src.utils.map_geometry.project_game_to_screen` using the supplied
    player/scale/center context, so the resulting ``points`` are ready for the
    render layer. A Section with ``n`` nodes yields ``n`` points and therefore
    ``max(0, n - 1)`` ordered segments (Requirements 5.3, 5.7); every node uses
    the uniform :data:`PATH_NODE_ICON_KEY` icon (Requirement 5.2).

    State filtering (Requirements 5.5, 5.6): layers are produced **only** when
    the route's ``state_id`` matches ``context_state_id``. When they differ this
    returns an empty tuple, so no route content is drawn and other overlays are
    left untouched.
    """
    if route.state_id != context_state_id:
        return ()

    layers = []
    for section in route.sections:
        points = tuple(
            project_game_to_screen(
                node.x, node.y, player_x, player_y, scale, center_x, center_y
            )
            for node in section.nodes
        )
        node_ids = tuple(node.position_id for node in section.nodes)
        layers.append(
            PathLayer(color=section.color, points=points, node_ids=node_ids)
        )
    return tuple(layers)


__all__ = [
    "PathNode",
    "Section",
    "PathRoute",
    "PathLayer",
    "PathParseError",
    "parse_path_route",
    "load_path_route",
    "parse_section_color",
    "build_path_layers",
    "DEFAULT_SECTION_COLOR",
    "PATH_NODE_ICON_KEY",
]
