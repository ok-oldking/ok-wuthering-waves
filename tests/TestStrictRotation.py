"""Unit tests for the Augusta/Iuno/ShoreKeeper strict rotation coordinator.

These tests exercise only ``src.combat.StrictRotation`` with lightweight fakes,
so they run without the game stack (no cv2/ok/Qt) and stay fast in CI. The
per-character key sequences in ``perform_beat`` need the live game and are not
covered here; this protects the *ordering* contract that makes the rotation
strict.
"""
import unittest

from src.combat.StrictRotation import (
    StrictRotation, BEATS, LOOP_START, TEAM, MUST, NO, NORMAL, get_strict_rotation,
    build_concerto,
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


def team(*names):
    return [make_char(n) for n in names]


def target_team():
    return team('Augusta', 'Iuno', 'ShoreKeeper')


EXPECTED_OPENER = [
    'Augusta', 'Iuno', 'ShoreKeeper', 'Iuno', 'Augusta', 'Iuno',
    'ShoreKeeper', 'Iuno', 'Augusta', 'ShoreKeeper',
]
EXPECTED_LOOP = ['Augusta', 'Iuno', 'Augusta', 'Iuno', 'Augusta', 'ShoreKeeper']


class TestStrictRotation(unittest.TestCase):

    def test_beat_table_consistency(self):
        n = len(BEATS)
        self.assertFalse(BEATS[0].intro, 'opener must not start on an intro')
        for i in range(1, n):
            self.assertEqual(BEATS[i].intro, BEATS[i - 1].outro,
                             f'beat {i} {BEATS[i].name} intro != prev outro')
        self.assertEqual(BEATS[LOOP_START].intro, BEATS[n - 1].outro,
                         'loop wrap intro/outro mismatch')

    def test_no_consecutive_same_char(self):
        for i in range(1, len(BEATS)):
            self.assertNotEqual(BEATS[i].char, BEATS[i - 1].char, f'consecutive char at {i}')
        self.assertNotEqual(BEATS[-1].char, BEATS[LOOP_START].char, 'loop wrap repeats char')

    def test_beats_only_use_team_members(self):
        for beat in BEATS:
            self.assertIn(beat.char, TEAM)

    def test_full_order_opener_then_three_loops(self):
        rot = StrictRotation(FakeTask(target_team()))
        expected = EXPECTED_OPENER + EXPECTED_LOOP * 3
        order = []
        for _ in range(len(expected)):
            order.append(rot.current_beat().char)
            rot.advance()
        self.assertEqual(order, expected)

    def test_advance_wraps_to_loop_not_zero(self):
        rot = StrictRotation(FakeTask(target_team()))
        rot.index = len(BEATS) - 1
        rot.advance()
        self.assertEqual(rot.index, LOOP_START)
        for _ in range(200):
            rot.advance()
            self.assertGreaterEqual(rot.index, LOOP_START)

    def test_priority_must_for_current_no_for_others(self):
        rot = StrictRotation(FakeTask(target_team()))
        rot.index = 0  # aug_open
        self.assertEqual(rot.priority_for('Augusta'), MUST)
        self.assertEqual(rot.priority_for('Iuno'), NO)
        self.assertEqual(rot.priority_for('ShoreKeeper'), NO)
        rot.advance()  # iuno_open1
        self.assertEqual(rot.priority_for('Iuno'), MUST)
        self.assertEqual(rot.priority_for('Augusta'), NO)

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
        self.assertEqual(rot.priority_for('Augusta'), NORMAL)

    def test_active_when_config_missing_defaults_on(self):
        rot = StrictRotation(FakeTask(target_team(), char_config={}))
        self.assertTrue(rot.is_active())

    def test_resync_finds_nearest_future_beat(self):
        rot = StrictRotation(FakeTask(target_team()))
        rot.index = 0  # expects Augusta, but ShoreKeeper is on field
        self.assertTrue(rot.resync('ShoreKeeper'))
        self.assertEqual(rot.current_beat().char, 'ShoreKeeper')
        self.assertEqual(rot.index, 2)  # sk_open

    def test_resync_wraps_through_loop(self):
        rot = StrictRotation(FakeTask(target_team()))
        rot.index = len(BEATS) - 1  # sk_loop; next Augusta is loop start
        self.assertTrue(rot.resync('Augusta'))
        self.assertEqual(rot.index, LOOP_START)

    def test_maybe_reset_on_new_combat(self):
        task = FakeTask(target_team(), combat_start=100)
        rot = StrictRotation(task)
        rot.maybe_reset()
        rot.index = 12
        rot.maybe_reset()  # same combat -> keep position
        self.assertEqual(rot.index, 12)
        task.combat_start = 200  # new combat -> rewind to opener
        rot.maybe_reset()
        self.assertEqual(rot.index, 0)

    def test_run_current_executes_and_advances(self):
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        aug = task.chars[0]
        calls = []
        aug.perform_beat = lambda beat: calls.append(('perform', beat.name))
        aug.switch_next_char = lambda free_intro=False: calls.append(('switch', free_intro))
        rot.index = 0
        self.assertTrue(rot.run_current(aug))
        self.assertEqual(calls, [('perform', 'aug_open'), ('switch', False)])
        self.assertEqual(rot.index, 1)

    def test_run_current_outro_beat_builds_concerto_then_switches_plain(self):
        # Outro beats must NOT force an intro; they top off concerto and switch
        # normally so the engine grants a real intro only when the ring is full.
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()  # sync combat tracking so run_current won't rewind
        sk = task.chars[2]
        events = []
        sk.perform_beat = lambda beat: events.append(('beat', beat.name))
        # concerto becomes full once a basic attack has landed (no skills here)
        sk.is_con_full = lambda: ('click',) in events
        sk.echo_available = lambda: False  # force the contiguous-attack fallback
        sk.resonance_available = lambda: False
        sk.task = task
        sk.sleep = lambda *a, **k: None
        # the fallback now drives basics via continues_normal_attack, which bails
        # the instant the ring fills.
        sk.continues_normal_attack = lambda *a, **k: events.append(('click',))
        task.click = lambda *a, **k: events.append(('click',))
        sk.switch_next_char = lambda *a, **k: events.append(('switch', a, k))
        rot.index = 6  # sk_open2, outro=True
        self.assertTrue(rot.run_current(sk))
        # beat ran, concerto was topped off (one click while not full), then a
        # plain switch with no forced free_intro.
        self.assertEqual(events[0], ('beat', 'sk_open2'))
        self.assertIn(('click',), events)
        self.assertEqual(events[-1], ('switch', (), {}))

    def test_run_current_non_outro_beat_does_not_build_concerto(self):
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()
        aug = task.chars[0]
        events = []
        aug.perform_beat = lambda beat: events.append(('beat', beat.name))
        aug.is_con_full = lambda: self.fail('non-outro beat must not build concerto')
        aug.switch_next_char = lambda *a, **k: events.append(('switch', a, k))
        rot.index = 0  # aug_open, outro=False
        self.assertTrue(rot.run_current(aug))
        self.assertEqual(events, [('beat', 'aug_open'), ('switch', (), {})])

    def test_run_current_resets_to_opener_on_first_call(self):
        # _last_combat_start starts unset, so the first run_current rewinds to
        # the opener even if index was nudged beforehand.
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.index = 9
        aug = task.chars[0]
        aug.perform_beat = lambda beat: None
        aug.switch_next_char = lambda free_intro=False: None
        rot.run_current(aug)
        self.assertEqual(rot.index, 1)  # ran aug_open (0) then advanced to 1

    def test_run_current_inactive_returns_false(self):
        task = FakeTask(team('Augusta', 'Iuno', 'Verina'))
        rot = StrictRotation(task)
        aug = task.chars[0]
        aug.perform_beat = lambda beat: self.fail('should not run beat when inactive')
        aug.switch_next_char = lambda free_intro=False: None
        self.assertFalse(rot.run_current(aug))

    def test_run_current_inactive_has_no_side_effects(self):
        # When inactive the coordinator must not mutate state or reset (no log
        # spam / index churn for non-target teams).
        task = FakeTask(team('Augusta', 'Iuno', 'Verina'), combat_start=5)
        rot = StrictRotation(task)
        rot.index = 5
        rot._last_combat_start = 'sentinel'
        aug = task.chars[0]
        aug.perform_beat = lambda beat: self.fail('inactive must not run beat')
        self.assertFalse(rot.run_current(aug))
        self.assertEqual(rot.index, 5)
        self.assertEqual(rot._last_combat_start, 'sentinel')

    def test_run_current_advances_past_failing_beat(self):
        # An unexpected per-beat error must advance the index (so the same beat
        # is not retried forever) and propagate.
        task = FakeTask(target_team())
        rot = StrictRotation(task)
        rot.maybe_reset()
        aug = task.chars[0]
        aug.perform_beat = lambda beat: (_ for _ in ()).throw(ValueError('boom'))
        aug.switch_next_char = lambda *a, **k: self.fail('must not switch on failure')
        rot.index = 0
        with self.assertRaises(ValueError):
            rot.run_current(aug)
        self.assertEqual(rot.index, 1)

    def test_build_concerto_prefers_echo_and_skill_over_basics(self):
        # A healer's basics barely build concerto; build_concerto should recast
        # echo/skill when available rather than only basic-attacking.
        task = FakeTask(target_team())
        sk = task.chars[2]
        calls = []
        sk.echo_available = lambda: True
        sk.click_echo = lambda time_out=1: calls.append('echo') or True
        sk.resonance_available = lambda: True
        sk.click_resonance = lambda *a, **k: calls.append('skill') or (True, 0, False)
        # concerto fills once the skill has been recast (strong source)
        sk.is_con_full = lambda: 'skill' in calls
        sk.task = task
        sk.sleep = lambda *a, **k: None
        task.click = lambda *a, **k: calls.append('basic')
        self.assertTrue(build_concerto(sk))
        self.assertIn('echo', calls)
        self.assertIn('skill', calls)
        self.assertNotIn('basic', calls)  # strong sources fired, no basic fallback

    def test_build_concerto_falls_back_to_basics_when_skills_unavailable(self):
        task = FakeTask(target_team())
        sk = task.chars[2]
        calls = []
        sk.echo_available = lambda: False
        sk.resonance_available = lambda: False
        sk.is_con_full = lambda: 'basic' in calls  # fills after one basic slice
        sk.task = task
        sk.sleep = lambda *a, **k: None
        # the fallback drives basics through continues_normal_attack, which bails
        # the instant the ring fills (until_con_full=True).
        sk.continues_normal_attack = lambda *a, **k: calls.append('basic')
        task.click = lambda *a, **k: calls.append('basic')
        self.assertTrue(build_concerto(sk))
        self.assertEqual(calls, ['basic'])

    def test_build_concerto_uses_forte_when_supplied_and_skills_on_cd(self):
        # ShoreKeeper opts into a forte_check; when echo/skill are spent, the
        # top-off must recover via forte rather than only basic-attacking.
        task = FakeTask(target_team())
        sk = task.chars[2]
        calls = []
        sk.echo_available = lambda: False
        sk.resonance_available = lambda: False
        sk.is_mouse_forte_full = lambda: 'forte' not in calls  # full until used
        sk.heavy_click_forte = lambda fn: (calls.append('forte') or True)
        sk.is_con_full = lambda: 'forte' in calls  # fills once forte is spent
        sk.task = task
        sk.sleep = lambda *a, **k: None
        sk.continues_normal_attack = lambda *a, **k: calls.append('basic')
        self.assertTrue(build_concerto(sk, forte_check=sk.is_mouse_forte_full))
        self.assertIn('forte', calls)
        self.assertNotIn('basic', calls)  # forte filled it, no basic fallback

    def test_build_concerto_forte_check_default_skipped(self):
        # No forte_check (Augusta/Iuno): the forte branch must never run, even if
        # the char happens to expose is_mouse_forte_full/heavy_click_forte.
        task = FakeTask(target_team())
        sk = task.chars[2]
        calls = []
        sk.echo_available = lambda: False
        sk.resonance_available = lambda: False
        sk.is_mouse_forte_full = lambda: self.fail('forte must not be checked')
        sk.heavy_click_forte = lambda fn: self.fail('forte must not fire')
        sk.is_con_full = lambda: 'basic' in calls
        sk.task = task
        sk.sleep = lambda *a, **k: None
        sk.continues_normal_attack = lambda *a, **k: calls.append('basic')
        self.assertTrue(build_concerto(sk))
        self.assertEqual(calls, ['basic'])

    def test_build_concerto_times_out_returns_false(self):
        task = FakeTask(target_team())
        sk = task.chars[2]
        sk.is_con_full = lambda: False  # never fills
        sk.echo_available = lambda: False
        sk.resonance_available = lambda: False
        sk.task = task
        sk.sleep = lambda *a, **k: None
        sk.continues_normal_attack = lambda *a, **k: None
        task.click = lambda *a, **k: None
        self.assertFalse(build_concerto(sk, time_out=0.05))

    def test_get_strict_rotation_is_cached_per_task(self):
        task = FakeTask(target_team())
        first = get_strict_rotation(task)
        second = get_strict_rotation(task)
        self.assertIs(first, second)


if __name__ == '__main__':
    unittest.main()
