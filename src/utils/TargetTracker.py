"""Pure-logic target tracking for the map-overlay-interaction feature.

This module is part of the *pure-logic layer*: it has **no** dependency on
PySide6/Qt, the game runtime, OCR, or screen capture, so it can be imported and
tested on a development machine (conda env ``wuwa`` / local ``.venv``) without
pulling in Qt. It only depends on the equally Qt-free
:mod:`src.utils.PathRoute` model and :mod:`src.utils.map_geometry` distance
helper.

It implements the target-tracking state machine core that backs Path_Mode
navigation:

- ``TargetRef`` identifies the current target as a ``(section_id, index)`` pair.
- ``validate_threshold`` validates a configured Arrival_Threshold.
- ``TargetTracker`` advances the target one node at a time within a single
  Section, never crossing into another Section, clearing the target once the
  last node of a Section is passed, and debouncing arrival-triggered advances so
  a stationary player within the threshold only advances once per target.

Design references:
- design.md "Components and Interfaces" -> "TargetTracker"
- Requirements 7.1, 7.3, 7.4, 7.5, 7.6 (target set/replace/clear/uniqueness),
  9.1, 9.2, 9.3, 9.5, 9.6 (single-step advance, no cross-Section, debounce),
  9.8 (threshold validation).

Feature: map-overlay-interaction
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.utils.PathRoute import PathNode, PathRoute, Section
from src.utils.map_geometry import distance_game_units

__all__ = [
    "TargetRef",
    "TargetTracker",
    "validate_threshold",
    "right_click_dispatch",
    "THRESHOLD_MIN",
    "THRESHOLD_MAX",
]

# Inclusive valid range for the configurable Arrival_Threshold, in game units
# (Requirement 9.7 / 9.8).
THRESHOLD_MIN = 1
THRESHOLD_MAX = 100000


@dataclass(frozen=True)
class TargetRef:
    """Uniquely identifies the current Target.

    ``section_id`` is the owning Section's id; ``index`` is the zero-based
    position of the target node inside that Section's ``nodes`` tuple (i.e. its
    order in the JSON ``positionList``). ``None`` (a missing ``TargetRef``)
    represents the no-target state (Requirement 7.6).
    """

    section_id: int
    index: int


def validate_threshold(value) -> bool:
    """Return ``True`` iff ``value`` is a number within ``[1, 100000]``.

    The Arrival_Threshold is a configurable value measured in game units; the
    configuration layer calls this to reject invalid/out-of-range input and keep
    the previous valid value (Requirements 9.7, 9.8). Booleans and non-numeric
    values are rejected.
    """
    # ``bool`` is a subclass of ``int``; reject it explicitly so True/False are
    # never accepted as thresholds.
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    # Reject NaN (which fails all comparisons) and infinities.
    if value != value:  # NaN
        return False
    return THRESHOLD_MIN <= value <= THRESHOLD_MAX


def right_click_dispatch(
    target_ref: Optional[TargetRef],
    clicked_ref: TargetRef,
    clicked_id: str,
    completed_set,
):
    """Decide the outcome of a Path_Mode right-click on a node (pure logic).

    Encodes the unified right-click dispatch priority described in design.md
    ("OverlayController -> 右键分派优先级"): **target-cancel beats
    mark-toggle**.

    Parameters
    ----------
    target_ref:
        The current Target locator, or ``None`` when there is no target.
    clicked_ref:
        The locator of the right-clicked node.
    clicked_id:
        The right-clicked node's completion key (its ``position_id``), used to
        toggle membership in the completed set.
    completed_set:
        The current set of completed ids. Not mutated; a new set is returned.

    Returns
    -------
    ``(new_target, new_completed_set)`` where:

    - If the clicked node *is* the current Target: the Target is cleared
      (``new_target is None``) and the completed set is returned unchanged (the
      node's completion state is preserved, and its route data is untouched —
      this helper never removes nodes). (Requirements 6.3, 7.3)
    - If the clicked node is *not* the current Target: the Target is left
      unchanged and the node's completion state is toggled
      (uncompleted ↔ completed). (Requirements 6.1, 6.2, 7.4)
    """
    completed = set(completed_set)

    # Priority 1: cancelling the current Target. Completion state is preserved
    # and route data is never touched here.
    if target_ref is not None and clicked_ref == target_ref:
        return None, completed

    # Priority 2: toggle the clicked node's completion mark; Target unchanged.
    if clicked_id in completed:
        completed.discard(clicked_id)
    else:
        completed.add(clicked_id)
    return target_ref, completed


class TargetTracker:
    """Section-bounded target advancement state machine (pure logic).

    The tracker does not hold any Qt or game objects; it only reasons about a
    parsed :class:`~src.utils.PathRoute.PathRoute`, the current target locator,
    and player game-unit coordinates.
    """

    def __init__(self, route: PathRoute, arrival_threshold: float = 1000.0):
        if not validate_threshold(arrival_threshold):
            raise ValueError(
                f"arrival_threshold must be within [{THRESHOLD_MIN}, {THRESHOLD_MAX}]"
            )
        self._route = route
        self._arrival_threshold = float(arrival_threshold)
        self._target: Optional[TargetRef] = None
        # Debounce flag: True once an arrival-triggered advance has fired for the
        # current standstill. Reset when the player leaves the threshold zone or
        # the target is set/cleared/manually advanced (Requirement 9.2).
        self._arrival_triggered = False

    # -- target accessors ---------------------------------------------------

    @property
    def target(self) -> Optional[TargetRef]:
        """The current :class:`TargetRef`, or ``None`` when there is no target."""
        return self._target

    @property
    def arrival_threshold(self) -> float:
        """The arrival distance threshold in game units."""
        return self._arrival_threshold

    # -- target mutation ----------------------------------------------------

    def set_target(self, section_id: int, index: int) -> TargetRef:
        """Set (or replace) the current Target to a specific node.

        Validates that ``section_id`` names a Section in the route and that
        ``index`` is within that Section's nodes. Replacing an existing target
        discards the old one, keeping at most one target at any time
        (Requirements 7.1, 7.5, 7.6). Resets the arrival debounce so the freshly
        set target is eligible for auto-advance.

        Raises ``ValueError`` for an unknown ``section_id`` or out-of-range
        ``index``.
        """
        section = self._section_by_id(section_id)
        if section is None:
            raise ValueError(f"unknown section_id: {section_id}")
        if not (0 <= index < len(section.nodes)):
            raise ValueError(
                f"index {index} out of range for section {section_id} "
                f"(0..{len(section.nodes) - 1})"
            )
        self._target = TargetRef(section_id=section_id, index=index)
        self._arrival_triggered = False
        return self._target

    def clear_target(self) -> None:
        """Enter the no-target state, leaving route data untouched.

        Covers manual target cancellation (Requirement 7.3) and the
        end-of-Section stop (Requirement 9.5).
        """
        self._target = None
        self._arrival_triggered = False

    def advance(self) -> Optional[TargetRef]:
        """Advance the target one node within the same Section.

        Moves the target to the next node in the owning Section's order. If the
        current target is already the last node of its Section, clears the
        target and returns ``None`` (stop tracking; never cross into another
        Section). Returns the new :class:`TargetRef`, or ``None`` when there was
        no target or the Section ended (Requirements 9.1, 9.3, 9.5, 9.6).

        This is the manual (hotkey) advance path; it resets the arrival debounce
        so the new target is eligible for auto-advance.
        """
        result = self._step()
        self._arrival_triggered = False
        return result

    def maybe_auto_advance(self, player_x: float, player_y: float) -> bool:
        """Advance once if the player is within ``arrival_threshold`` of target.

        Returns whether an advance occurred. When the player is at or within the
        threshold distance of the current target node, advances a single node
        (Requirement 9.1). While the player stays within the threshold of the
        same target node, only the first call advances; subsequent calls are
        debounced until the player leaves the threshold zone (Requirement 9.2).

        ``player_x`` / ``player_y`` are expected to already be in game units (the
        OCR x100 conversion happens in the draw-item layer, Requirement 9.10).
        """
        node = self._current_node()
        if node is None:
            return False

        distance = distance_game_units(player_x, player_y, node.x, node.y)
        if distance > self._arrival_threshold:
            # Player is outside the arrival zone: re-arm the debounce so a later
            # arrival can trigger again.
            self._arrival_triggered = False
            return False

        # Within threshold.
        if self._arrival_triggered:
            return False

        # Fire a single-step advance and latch the debounce so a stationary
        # player within the zone does not cascade through the Section.
        self._step()
        self._arrival_triggered = True
        return True

    # -- internals ----------------------------------------------------------

    def _step(self) -> Optional[TargetRef]:
        """Move the target one node forward, or clear it at the Section end.

        Does not touch the arrival debounce flag; callers manage that.
        """
        if self._target is None:
            return None
        section = self._section_by_id(self._target.section_id)
        if section is None:
            # Defensive: target points at a section no longer in the route.
            self._target = None
            return None
        next_index = self._target.index + 1
        if next_index >= len(section.nodes):
            # Already at the last node of this Section: stop, do not cross over.
            self._target = None
            return None
        self._target = TargetRef(section_id=self._target.section_id, index=next_index)
        return self._target

    def _section_by_id(self, section_id: int) -> Optional[Section]:
        for section in self._route.sections:
            if section.section_id == section_id:
                return section
        return None

    def _current_node(self) -> Optional[PathNode]:
        if self._target is None:
            return None
        section = self._section_by_id(self._target.section_id)
        if section is None or not (0 <= self._target.index < len(section.nodes)):
            return None
        return section.nodes[self._target.index]
