"""Strict, frame-checked rotation coordinator for the Augusta / Iuno / ShoreKeeper team.

The default combat engine (``BaseCombatTask.switch_next_char``) is *reactive*:
it picks the next on-field character from role + concerto + buff timers. That
is great for arbitrary teams but it cannot follow a hand-authored rotation that
visits the same character several times with different actions each time.

This module adds an opt-in *scripted* layer on top of the reactive engine for
one specific team. A fixed list of "beats" (``BEATS``) encodes the user's
rotation as ``opener`` (played once) + ``loop`` (repeated). Each beat names the
character that should be on field and whether it is entered via an intro and
left via a concerto outro. The coordinator only enforces *ordering*; the actual
per-beat key sequences live in each character's ``perform_beat`` so they can use
that character's own frame-checked helpers (``click_liberation``,
``perform_majesty``, ``do_everything`` ...).

AI editing guide:
- This file is intentionally free of heavy imports (no ``cv2`` / ``ok`` at module
  load) so the pure ordering logic stays unit-testable without the game stack.
  Keep it that way -- talk to characters/task only through duck-typed attributes.
- Ordering is driven through ``priority_for`` which the three character classes
  translate into ``SwitchPriority`` inside their ``get_switch_priority`` override.
- Everything degrades gracefully: if the live team is not the target trio, if the
  config toggle is off, or if the script desyncs from what is actually on screen,
  the characters fall back to their original reactive ``do_perform``.
"""

import time
from collections import namedtuple

try:  # keep this module importable without the full game stack (tests / tooling)
    from ok import Logger

    logger = Logger.get_logger(__name__)
except Exception:  # pragma: no cover - exercised only when ``ok`` is unavailable
    import logging

    logger = logging.getLogger(__name__)

# Priority tokens returned by the coordinator. The character classes map these to
# ``src.char.BaseChar.SwitchPriority`` so this module need not import it.
MUST = 'must'
NO = 'no'
NORMAL = 'normal'

CONFIG_KEY = 'Augusta Iuno SK Strict Rotation'

# Class names of the team this rotation is written for.
TEAM = frozenset({'Augusta', 'Iuno', 'ShoreKeeper'})

# A single step of the rotation.
#   name  : unique id, dispatched on by ``<Char>.perform_beat``
#   char  : class name of the character that must be on field for this beat
#   intro : True when this beat is entered through an intro (previous beat outro'd)
#   outro : True when this beat builds concerto to full and leaves via an outro
Beat = namedtuple('Beat', ['name', 'char', 'intro', 'outro'])

# The rotation, transcribed from the user's step list.
#
#   Opener (played once):
#     1  Aug  skill
#     2  Iuno skill
#     3  Sk   ba123 lib ba12 ha skill
#     4  Iuno skill
#     5  Aug  ha
#     6  Iuno echo
#     7  Sk   ba12345 ha outro
#     8  Iuno intro, jump-cancel, lib, skill, ba1234, skill, ba, ha, outro
#     9  Aug  intro, ha, lib (griffin), skill, ha, 2nd lib, [ba123 ha], echo, outro
#    10  Sk   super intro, build concerto, outro
#
#   Loop (repeats):
#    11  Aug  intro, ha
#    12  Iuno skill, echo, dash, skill
#    13  Aug  skill, ha
#    14  Iuno jump, lib, skill, ba1234, skill, ba, ha, outro
#    15  Aug  ha, lib (griffin), skill, ha, 2nd lib, ba123, ha, echo, outro
#    16  Sk   super intro, build concerto, outro  -> back to 11
#
# ``intro`` of beat N always equals ``outro`` of beat N-1 (with loop wraparound),
# i.e. an outro on one beat hands the next beat its intro.
BEATS = [
    # opener
    Beat('aug_open',    'Augusta',     intro=False, outro=False),
    Beat('iuno_open1',  'Iuno',        intro=False, outro=False),
    Beat('sk_open',     'ShoreKeeper', intro=False, outro=False),
    Beat('iuno_open2',  'Iuno',        intro=False, outro=False),
    Beat('aug_open2',   'Augusta',     intro=False, outro=False),
    Beat('iuno_open3',  'Iuno',        intro=False, outro=False),
    Beat('sk_open2',    'ShoreKeeper', intro=False, outro=True),
    Beat('iuno_burst',  'Iuno',        intro=True,  outro=True),
    Beat('aug_burst',   'Augusta',     intro=True,  outro=True),
    Beat('sk_intro',    'ShoreKeeper', intro=True,  outro=True),
    # loop
    Beat('aug_loop1',   'Augusta',     intro=True,  outro=False),
    Beat('iuno_loop1',  'Iuno',        intro=False, outro=False),
    Beat('aug_loop2',   'Augusta',     intro=False, outro=False),
    Beat('iuno_burst2', 'Iuno',        intro=False, outro=True),
    Beat('aug_burst2',  'Augusta',     intro=True,  outro=True),
    Beat('sk_loop',     'ShoreKeeper', intro=True,  outro=True),
]

# Index of the first loop beat; ``advance`` wraps here instead of to 0 so the
# opener is never replayed mid-combat.
LOOP_START = 10


class StrictRotation:
    """Tracks the current beat and enforces the scripted switch order.

    A single instance is attached to the combat task (``task._strict_rotation``)
    and lives for the whole combat. It is reset whenever a new combat starts.
    """

    def __init__(self, task):
        self.task = task
        self.index = 0
        self._last_combat_start = None

    # --- team / enablement -------------------------------------------------
    def team_names(self):
        chars = getattr(self.task, 'chars', None) or []
        return {type(c).__name__ for c in chars if c is not None}

    def team_matches(self):
        return self.team_names() == set(TEAM)

    def config_enabled(self):
        char_config = getattr(self.task, 'char_config', None)
        if char_config is None:
            return True
        try:
            return bool(char_config.get(CONFIG_KEY, True))
        except Exception:
            return True

    def is_active(self):
        return self.config_enabled() and self.team_matches()

    # --- beat bookkeeping --------------------------------------------------
    def maybe_reset(self):
        """Rewind to the opener when a fresh combat is detected."""
        combat_start = getattr(self.task, 'combat_start', None)
        if combat_start != self._last_combat_start:
            self._last_combat_start = combat_start
            self.index = 0
            logger.info('StrictRotation reset to opener for new combat')

    def current_beat(self):
        return BEATS[self.index]

    def advance(self):
        self.index += 1
        if self.index >= len(BEATS):
            self.index = LOOP_START
        return self.current_beat()

    def resync(self, char_name):
        """Point the script at the next upcoming beat for ``char_name``.

        Used when the on-field character does not match the expected beat (combat
        started on a different character, a switch was missed, etc.). Searches
        forward from the current beat through the loop so recovery prefers the
        nearest future beat. Returns True if a matching beat was found.
        """
        for offset in range(len(BEATS)):
            idx = self.index + offset
            if idx >= len(BEATS):
                idx = LOOP_START + ((idx - len(BEATS)) % (len(BEATS) - LOOP_START))
            if BEATS[idx].char == char_name:
                if idx != self.index:
                    logger.info(f'StrictRotation resync {self.index} -> {idx} for {char_name}')
                self.index = idx
                return True
        return False

    # --- ordering ----------------------------------------------------------
    def priority_for(self, char_name):
        """Switch priority for ``char_name`` when choosing the next on-field char.

        The coordinator's current beat is the character that should come next, so
        it gets ``MUST`` and the others get ``NO``. Returns ``NORMAL`` when the
        script is inactive so the reactive engine takes over.
        """
        if not self.is_active():
            return NORMAL
        return MUST if self.current_beat().char == char_name else NO

    # --- driver ------------------------------------------------------------
    def run_current(self, char):
        """Execute the current beat for ``char`` and queue the next switch.

        Returns True if the beat was handled (the caller should return), or False
        to fall back to the character's default rotation.
        """
        self.maybe_reset()
        if not self.is_active():
            return False
        beat = self.current_beat()
        if beat.char != char.name:
            if not self.resync(char.name):
                logger.info(f'StrictRotation cannot place {char.name}, falling back')
                return False
            beat = self.current_beat()
        logger.info(f'StrictRotation beat {self.index} {beat.name} ({char.name}) '
                    f'intro={beat.intro} outro={beat.outro}')
        char.perform_beat(beat)
        if beat.outro:
            # An outro hands the NEXT character its intro, but the game only
            # grants an intro when this character's concerto ring is actually
            # full. Top it off here and then switch normally so the engine
            # detects the full ring and fires a real intro. Forcing free_intro
            # while the ring is below full fakes an intro the game never plays:
            # switch_out then wrongly zeroes the concerto and the burst window
            # never lines up. (No built-in character forces free_intro either.)
            build_concerto(char)
        self.advance()
        char.switch_next_char()
        return True


def get_strict_rotation(task):
    """Return the task's :class:`StrictRotation`, creating it on first use."""
    rot = getattr(task, '_strict_rotation', None)
    if rot is None:
        rot = StrictRotation(task)
        try:
            task._strict_rotation = rot
        except Exception:  # pragma: no cover - task may forbid attribute set in tests
            pass
    return rot


# --- shared frame-checked action helpers ----------------------------------
# Small primitives reused by the per-character ``perform_beat`` implementations.

def basic_attacks(char, n, interval=0.12):
    """Send an ``n``-hit basic-attack string (the user's ``ba123`` notation)."""
    for _ in range(max(0, n)):
        char.task.click()
        char.sleep(interval)


def dash(char):
    """Perform a dodge/dash (the user's ``dash`` step) via the Dodge Key."""
    key = char.task.key_config.get('Dodge Key', 'lshift')
    char.task.send_key(key, after_sleep=0.05)


def heavy(char):
    """Heavy attack, preferring the forte-charged heavy when it is available."""
    if char.is_forte_full():
        if char.heavy_click_forte(char.is_forte_full):
            return
    char.heavy_attack()


def build_concerto(char, time_out=2.5):
    """Basic-attack until the concerto ring is full so the next swap can outro."""
    start = time.time()
    while time.time() - start < time_out:
        if char.is_con_full():
            return True
        char.task.click()
        char.sleep(0.1)
    return char.is_con_full()
