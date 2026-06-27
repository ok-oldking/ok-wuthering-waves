"""Staged rotation coordinator for the Augusta / Iuno / ShoreKeeper team.

The default combat engine (``BaseCombatTask.switch_next_char``) is *reactive*: it
picks the next on-field character from role + concerto + buff timers. This module
adds an opt-in *staged* layer on top of it for one specific team.

Three stages cycle:

    Stage 1  ShoreKeeper   (heal + build concerto)
    Stage 2  Iuno          (buff burst -> buffs Augusta)
    Stage 3  Augusta       (full damage, under Iuno's buff)
    -> back to Stage 1

Each stage runs that character's actions, and only ADVANCES to the next stage when
that character's OUTRO actually fires -- i.e. concerto reaches full so the swap is a
coordinated outro (which is what transfers a character's outro buff to the next one).
If the outro is not fulfilled, the character stays on field and redoes their actions
until it fires; each attempt is bounded by a short time budget so it never hangs.

AI editing guide:
- This file avoids heavy imports (no ``cv2`` / ``ok`` at module load) so the pure
  stage logic stays unit-testable without the game stack. Talk to characters/task
  only through duck-typed attributes.
- Stage ordering is enforced through ``priority_for`` which the three character
  classes translate into ``SwitchPriority`` inside their ``get_switch_priority``.
- Each character implements ``perform_stage(self)`` (its on-field kit for its stage).
- Everything degrades gracefully: if the live team is not the target trio, the config
  toggle is off, or the script desyncs, characters fall back to their reactive
  ``do_perform``.
"""

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

# The stage cycle, by character class name. ShoreKeeper -> Iuno -> Augusta -> ...
# so Iuno always buffs Augusta right before Augusta's damage window.
STAGES = ['ShoreKeeper', 'Iuno', 'Augusta']

# Per-attempt bounded top-off toward full concerto. The stage's kit does the bulk
# of the work; this only finishes the last sliver (and lets the last action's
# concerto register) so the immediately-following swap is read as a full-concerto
# outro. It exits the instant the ring is full, so it is not an open-ended wait;
# if it cannot fill in time the stage simply redoes on the next perform() call.
STAGE_GATE_TIME_OUT = 2.0

# Give up the outro gate after this many failed attempts on a stage and switch
# anyway (a plain swap, no outro buff that cycle) so a character that genuinely
# cannot reach full concerto -- liberation on cooldown, weak generation, etc. --
# can never stall the whole rotation on one stage.
MAX_STAGE_ATTEMPTS = 3


class StrictRotation:
    """Tracks the current stage and gates each stage on its outro firing.

    A single instance is attached to the combat task (``task._strict_rotation``)
    and lives for the whole combat. It is reset whenever a new combat starts.
    """

    def __init__(self, task):
        self.task = task
        self.stage = 0
        self.attempts = 0  # failed outro attempts on the current stage
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

    # --- stage bookkeeping -------------------------------------------------
    def maybe_reset(self):
        """Rewind to stage 1 when a fresh combat is detected."""
        combat_start = getattr(self.task, 'combat_start', None)
        if combat_start != self._last_combat_start:
            self._last_combat_start = combat_start
            self.stage = 0
            self.attempts = 0
            logger.info('StrictRotation reset to stage 1 for new combat')

    def current_char(self):
        return STAGES[self.stage]

    def advance(self):
        self.stage = (self.stage + 1) % len(STAGES)
        self.attempts = 0  # fresh stage starts with a clean attempt count
        return self.current_char()

    def resync(self, char_name):
        """Point the cycle at the stage for ``char_name`` (combat may start on any
        character, or a switch may be missed). Returns True if it has a stage."""
        if char_name in STAGES:
            idx = STAGES.index(char_name)
            if idx != self.stage:
                logger.info(f'StrictRotation resync stage {self.stage} -> {idx} for {char_name}')
                self.stage = idx
                self.attempts = 0
            return True
        return False

    # --- ordering ----------------------------------------------------------
    def priority_for(self, char_name):
        """Switch priority for ``char_name``. The current stage's character is the
        one that should be on field next, so it gets MUST and the others NO.
        Returns NORMAL when inactive so the reactive engine takes over."""
        if not self.is_active():
            return NORMAL
        return MUST if self.current_char() == char_name else NO

    # --- driver ------------------------------------------------------------
    def run_current(self, char):
        """Run ``char``'s stage once and, if its outro is fulfilled, advance + switch.

        Returns True if the stage was handled (caller should return), or False to
        fall back to the character's default rotation.
        """
        if not self.is_active():
            return False
        self.maybe_reset()
        if self.current_char() != char.name:
            if not self.resync(char.name):
                logger.info(f'StrictRotation cannot place {char.name}, falling back')
                return False
        logger.info(f'StrictRotation stage {self.stage} ({char.name})')
        try:
            char.perform_stage()
        except _combat_control_exceptions():
            raise  # combat ended / char dead -> let the task loop handle it

        # Gate: the swap only transfers this character's outro buff when concerto
        # reads exactly full at swap time. Top off briefly (bounded) so the last
        # action's concerto registers; if full, advance the stage and switch (the
        # swap fires as an outro). If still not full, stay on field and redo the
        # stage on the next perform() call -- "redo until the outro fires".
        if not char.is_con_full():
            self.task.wait_until(char.is_con_full, post_action=char.click_with_interval,
                                 time_out=STAGE_GATE_TIME_OUT)
        if char.is_con_full():
            self._advance_and_switch(char)
            return True

        # Outro not fulfilled this attempt. Redo the stage -- but give up after
        # MAX_STAGE_ATTEMPTS and switch anyway (a plain swap, no outro buff this
        # cycle) so a character that cannot reach full concerto never stalls the
        # whole rotation on one stage.
        self.attempts += 1
        if self.attempts >= MAX_STAGE_ATTEMPTS:
            logger.warning(f'StrictRotation stage {char.name}: outro not fulfilled after '
                           f'{self.attempts} attempts; giving up and switching anyway')
            self._advance_and_switch(char)
            return True
        # The intro animation only plays on the first beat after a swap-in; clear
        # the intro flags so perform_stage does not re-run its intro wait
        # (_intro_wait / wait_down) on every redo beat.
        char.has_intro = False
        char.has_sub_dps_intro = False
        logger.info(f'StrictRotation stage {char.name}: outro not fulfilled '
                    f'(attempt {self.attempts}/{MAX_STAGE_ATTEMPTS}); redoing stage')
        return True

    def _advance_and_switch(self, char):
        """Advance the stage and switch to the next character.

        advance() must run before switch_next_char so priority_for marks the next
        stage's character MUST. If the swap aborts (e.g. combat ended raises), undo
        the advance so the stage is not left half-advanced; resync/maybe_reset will
        re-place it on recovery.
        """
        self.advance()
        try:
            char.switch_next_char()
        except Exception:
            self.stage = (self.stage - 1) % len(STAGES)
            raise


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


def _combat_control_exceptions():
    """Combat-flow exceptions that must propagate, not be swallowed as stage errors.

    Imported lazily so this module stays importable without the game stack;
    returns an empty tuple if the import is unavailable.
    """
    try:
        from src.task.BaseCombatTask import NotInCombatException, CharDeadException
        return (NotInCombatException, CharDeadException)
    except Exception:  # pragma: no cover - only when the game stack is absent
        return tuple()


# --- shared frame-checked action helpers ----------------------------------
# Small primitives reused by the per-character ``perform_stage`` implementations.

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
