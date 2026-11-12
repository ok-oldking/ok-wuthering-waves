import unittest
from unittest.mock import Mock, patch

from ok import Box
from src.scene.WWScene import WWScene
from src.task.BaseCombatTask import BaseCombatTask
from src.task.AutoPickTask import AutoPickTask


class AutoPickAbyssTest(unittest.TestCase):
    def setUp(self):
        self.pick = AutoPickTask.__new__(AutoPickTask)
        self.pick.scene = WWScene()
        self.pick.in_team_and_world = Mock(return_value=True)
        self.combat = BaseCombatTask.__new__(BaseCombatTask)
        self.combat.scene = self.pick.scene
        self.combat._in_combat = False
        self.combat._abyss_combat_active = False
        self.combat._abyss_force_combat_until = 0
        self.marker = Box(500, 400, 80, 60, name='abyss_tower_start_marker')
        self.combat.find_abyss_start_marker = Mock(return_value=self.marker)
        self.combat.load_chars = Mock(return_value=True)
        self.combat.in_team = Mock(return_value=(True, 0, 3))
        self.combat.log_info = Mock()
        self.pick.get_task_by_class = Mock(return_value=self.combat)
        self.clock = patch('src.task.BaseCombatTask.time.monotonic', return_value=100)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)

    def observe(self, when, has_f, marker):
        self.now.return_value = when
        self.combat.find_abyss_start_marker.return_value = self.marker if marker else None
        return self.combat.check_abyss_start(has_f)

    def test_force_only_after_both_disappear(self):
        self.assertFalse(self.observe(100, True, True))
        self.assertFalse(self.combat._in_combat)
        self.assertTrue(self.observe(100.1, False, False))
        self.assertTrue(self.combat._in_combat)
        self.assertTrue(self.combat._abyss_combat_active)
        self.assertEqual(self.combat._abyss_force_combat_until, 105)
        self.combat.load_chars.assert_called_once()
        self.assertTrue(self.pick.scene.in_combat())
        self.assertFalse(self.observe(100.2, False, False))

    def test_marker_may_linger_up_to_half_second(self):
        self.observe(100, True, True)
        self.assertFalse(self.observe(100.2, False, True))
        self.assertFalse(self.combat._in_combat)
        self.assertTrue(self.observe(100.7, False, False))
        self.assertEqual(self.combat._abyss_force_combat_until, 105)

    def test_late_disappearance_does_not_force_combat(self):
        self.observe(100, True, True)
        self.assertFalse(self.observe(100.3, False, True))
        self.assertFalse(self.observe(100.801, False, False))
        self.combat.load_chars.assert_not_called()
        self.assertIsNone(self.pick.scene.abyss_start_seen_at)

    def test_last_joint_sighting_refreshes_time(self):
        self.observe(100, True, True)
        self.observe(102, True, True)
        self.assertTrue(self.observe(102.4, False, False))
        self.assertEqual(self.combat._abyss_force_combat_until, 107)

    def test_expired_joint_sighting_cannot_force_combat(self):
        self.observe(100, True, True)
        self.assertFalse(self.observe(105, False, False))
        self.combat.load_chars.assert_not_called()

    def test_marker_disappearing_while_f_remains_disarms(self):
        self.observe(100, True, True)
        self.assertFalse(self.observe(100.1, True, False))
        self.assertFalse(self.observe(100.2, False, False))
        self.combat.load_chars.assert_not_called()

    def test_absent_f_without_joint_sighting_does_nothing(self):
        self.assertFalse(self.observe(100, False, False))
        self.combat.find_abyss_start_marker.assert_not_called()
        self.combat.load_chars.assert_not_called()

    def test_team_or_character_load_failure_does_not_force(self):
        for in_team, loaded in ((False, True), (True, False)):
            with self.subTest(in_team=in_team, loaded=loaded):
                self.observe(100, True, True)
                self.combat.in_team.return_value = (in_team, 0, 3)
                self.combat.load_chars.return_value = loaded
                self.assertFalse(self.observe(100.1, False, False))
                self.assertFalse(self.combat._in_combat)
                self.assertEqual(self.combat._abyss_force_combat_until, 0)

    def test_run_checks_disappearance_and_clears_on_leaving_team(self):
        self.pick.get_box_by_name = Mock(return_value=Box(10, 10, 20, 20))
        self.pick.find_one = Mock(return_value=None)
        self.observe(100, True, True)
        self.now.return_value = 100.2
        self.combat.find_abyss_start_marker.return_value = False
        self.assertTrue(self.pick.run())
        self.observe(101, True, True)
        self.pick.scene.reset()
        self.pick.in_team_and_world.return_value = False
        self.pick.run()
        self.assertIsNone(self.pick.scene.abyss_start_seen_at)

    def test_auto_pick_clears_pending_manual_start(self):
        self.observe(100, True, True)
        self.pick.send_key = Mock()
        self.pick.sleep = Mock()
        self.pick.send_fs()
        self.assertIsNone(self.pick.scene.abyss_start_seen_at)
        self.assertFalse(self.observe(100.1, False, False))
        self.combat.load_chars.assert_not_called()

    def test_frame_reset_preserves_pending_start(self):
        self.observe(100, True, True)
        self.pick.scene.reset()
        self.assertTrue(self.observe(100.1, False, False))

    def test_other_combat_task_can_consume_shared_sighting(self):
        self.observe(100, True, True)
        other = BaseCombatTask.__new__(BaseCombatTask)
        other.scene = self.pick.scene
        other.find_abyss_start_marker = Mock(return_value=False)
        other.in_team = Mock(return_value=(True, 0, 3))
        other.load_chars = Mock(return_value=True)
        other.log_info = Mock()
        self.now.return_value = 100.2
        self.assertTrue(other.check_abyss_start(False))
        self.assertTrue(other._in_combat)
        self.assertEqual(other._abyss_force_combat_until, 105)
        self.assertIsNone(self.pick.scene.abyss_start_seen_at)

    def test_disappearance_checks_stay_near_last_marker(self):
        self.observe(100, True, True)
        self.combat.find_abyss_start_marker.assert_called_with(box=None)
        self.pick.scene.reset()
        self.observe(100.1, False, True)
        region = self.combat.find_abyss_start_marker.call_args.kwargs['box']
        self.assertEqual(region.center(), self.marker.center())
        self.assertEqual((region.width, region.height), (120, 90))
        self.observe(100.2, False, False)
        self.combat.find_abyss_start_marker.assert_called_with(box=region)
        self.assertIsNone(self.pick.scene.abyss_start_marker_box)

    def test_both_templates_are_matched_only_inside_supplied_region(self):
        region = self.marker.scale(1.5)
        self.combat.find_one = Mock(return_value=None)
        self.combat.box_of_screen = Mock()
        self.assertIsNone(BaseCombatTask.find_abyss_start_marker(self.combat, box=region))
        self.combat.box_of_screen.assert_not_called()
        self.assertEqual([call.args[0] for call in self.combat.find_one.call_args_list],
                         ['abyss_start_marker', 'abyss_tower_start_marker'])
        for call in self.combat.find_one.call_args_list:
            self.assertIs(call.kwargs['box'], region)


if __name__ == '__main__':
    unittest.main()
