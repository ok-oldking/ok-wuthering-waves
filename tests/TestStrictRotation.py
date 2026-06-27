"""Unit tests for the Augusta/Iuno/ShoreKeeper staged rotation coordinator.

These exercise only ``src.combat.StrictRotation`` with lightweight fakes, so they
run without the game stack (no cv2/ok/Qt). They cover the stage cycle, the
switch-ordering priority, and the outro gate (advance only when concerto is full,
otherwise stay on field and redo the stage).
"""
import unittest

from src.combat.StrictRotation import (
    StrictRotation, STAGES, TEAM, MUST, NO, NORMAL, MAX_STAGE_ATTEMPTS, get_strict_rotation,
)


def make_char(cls_name):
    """A minimal stand-in whose ``type(...).__name__`` is ``cls_name``."""
    cls = type(cls_name, (object,), {})
    obj = cls()
    obj.name = cls_name
    return obj


class FakeTask:
    def __init__(self, chars, combat_start=0, char_config=None):
        self.chars = chars
        self.combat_start = combat_start
        self.char_config = {} if char_config is None else char_config
        self.wait_until_calls = []

    def wait_until(self, condition, post_action=None, time_out=None):
        # Record the gate attempt; do not change state (tests control is_con_full).
        self.wait_until_calls.append(time_out)
        return condition()


def team(*names):
    return [make_char(n) for n in names]


def target_team():
    return team('Augusta', 'Iuno', 'ShoreKeeper')


def wire_char(char, task, *, con_full):
    """Give a fake char the attributes run_current touches."""
    events = []
    char.task = task
    char.perform_stage = lambda: events.append('perform')
    char.is_con_full = lambda: con_full
    char.click_with_interval = lambda *a, **k: None
    char.switch_next_char = lambda *a, **k: events.append('switch')
    return events


class TestStrictRotation(unittest.TestCase):

    def test_stage_cycle_sk_iuno_augusta(self):
        rot = StrictRotation(FakeTask(target_team()))
        self.assertEqual(STAGES, ['ShoreKeeper', 'Iuno', 'Augusta'])
        seen = [rot.current_char()]
        for _ in range(5):
            rot.advance()
            seen.append(rot.current_char())
        self.assertEqual(seen, ['ShoreKeeper', 'Iuno', 'Augusta',
                                'ShoreKeeper', 'Iuno', 'Augusta'])

    def test_stages_are_team_members(self):
        for c in STAGES:
            self.assertIn(c, TEAM)
        self.assertEqual(set(STAGES), set(TEAM))

    def test_priority_must_for_current_stage(self):
        rot = StrictRotation(FakeTask(target_team()))
        rot.stage = 0  # ShoreKeeper
        self.assertEqual(rot.priority_for('ShoreKeeper'), MUST)
        self.assertEqual(rot.priority_for('Iuno'), NO)
        self.assertEqual(rot.priority_for('Augusta'), NO)
        rot.advance()  # Iuno
        self.assertEqual(rot.priority_for('Iuno'), MUST)
        self.assertEqual(rot.priority_for('ShoreKeeper'), NO)

    def test_inactive_when_team_mismatch(self):
        rot = StrictRotation(FakeTask(team('Augusta', 'Iuno', 'Verina')))
        self.assertFalse(rot.team_matches())
        self.assertFalse(rot.is_active())
        self.assertEqual(rot.priority_for('Augusta'), NORMAL)

    def test_inactive_with_partial_team(self):
        rot = StrictRotation(FakeTask(team('Augusta', 'Iuno')))
        self.assertFalse(rot.is_active())

    def test_inactive_when_config_off(self):
        rot = StrictRotation(FakeTask(
            target_team(), char_config={'Augusta Iuno SK Strict Rotation': False}))
        self.assertTrue(rot.team_matches())
        self.assertFalse(rot.config_enabled())
        self.assertFalse(rot.is_active())
        self.assertEqual(rot.priority_for('ShoreKeeper'), NORMAL)

    def test_active_when_config_missing_defaults_on(self):
        rot = StrictRotation(FakeTask(target_team(), char_config={}))
        self.assertTrue(rot.is_active())

    def test_resync_points_at_chars_stage(self):
        rot = StrictRotation(FakeTask(target_team()))
        rot.stage = 0  # ShoreKeeper
        self.assertTrue(rot.resync('Augusta'))
        self.assertEqual(rot.current_char(), 'Augusta')
        self.assertEqual(rot.stage, STAGES.index('Augusta'))
        self.assertFalse(rot.resync('Verina'))

    def test_maybe_reset_on_new_combat(self):
        task = FakeTask(target_team(), combat_start=100)
        rot = StrictRotation(task)
        rot.maybe_reset()
        rot.stage = 2
        rot.maybe_reset()  # same combat -> keep position
        self.assertEqual(rot.stage, 2)
        task.combat_start = 200  # new combat -> rewind to stage 1
        rot.maybe_reset()
        self.assertEqual(rot.stage, 0)

    def test_run_current_advances_and_switches_when_con_full(self):
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()  # sync combat tracking
        sk = task.chars[2]
        events = wire_char(sk, task, con_full=True)
        rot.stage = 0  # ShoreKeeper's stage
        self.assertTrue(rot.run_current(sk))
        self.assertEqual(events, ['perform', 'switch'])
        self.assertEqual(rot.stage, 1)  # advanced to Iuno
        self.assertEqual(task.wait_until_calls, [])  # already full -> no gate wait

    def test_run_current_stays_and_redoes_when_not_full(self):
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()
        sk = task.chars[2]
        events = wire_char(sk, task, con_full=False)
        rot.stage = 0
        self.assertTrue(rot.run_current(sk))
        self.assertEqual(events, ['perform'])      # performed but did NOT switch
        self.assertEqual(rot.stage, 0)             # stayed on the same stage (redo)
        self.assertEqual(rot.attempts, 1)          # one failed attempt recorded
        self.assertEqual(len(task.wait_until_calls), 1)  # gate attempt was made

    def test_run_current_gives_up_after_max_attempts(self):
        # After MAX_STAGE_ATTEMPTS failed outro attempts the stage switches anyway
        # (plain swap) so a character that can't fill concerto never stalls.
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()
        sk = task.chars[2]
        events = wire_char(sk, task, con_full=False)
        rot.stage = 0
        for _ in range(MAX_STAGE_ATTEMPTS - 1):
            rot.run_current(sk)
            self.assertEqual(rot.stage, 0)         # still redoing
            self.assertEqual(events[-1], 'perform')  # no switch yet
        # final attempt -> give up and switch
        rot.run_current(sk)
        self.assertEqual(events[-1], 'switch')     # switched anyway
        self.assertEqual(rot.stage, 1)             # advanced to next stage
        self.assertEqual(rot.attempts, 0)          # counter reset for new stage

    def test_run_current_inactive_returns_false_no_perform(self):
        task = FakeTask(team('Augusta', 'Iuno', 'Verina'))
        rot = StrictRotation(task)
        aug = task.chars[0]
        aug.perform_stage = lambda: self.fail('must not perform when inactive')
        self.assertFalse(rot.run_current(aug))

    def test_run_current_resyncs_to_on_field_char(self):
        # combat starts on Augusta though stage defaults to ShoreKeeper
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()
        aug = task.chars[0]
        events = wire_char(aug, task, con_full=False)
        rot.stage = 0  # ShoreKeeper, but Augusta is on field
        self.assertTrue(rot.run_current(aug))
        self.assertEqual(rot.current_char(), 'Augusta')  # resynced to Augusta's stage
        self.assertEqual(events, ['perform'])

    def test_get_strict_rotation_is_cached_per_task(self):
        task = FakeTask(target_team())
        self.assertIs(get_strict_rotation(task), get_strict_rotation(task))


if __name__ == '__main__':
    unittest.main()
