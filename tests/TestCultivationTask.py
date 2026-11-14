import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from ok import Box
from src.task.BaseCombatTask import NotInCombatException
from src.task.CultivationTask import CultivationError, CultivationTask, MaterialGoal, MaterialRow
from src.task.DomainTask import DomainTask


class TestCultivationTask(unittest.TestCase):

    def setUp(self):
        self.task = CultivationTask.__new__(CultivationTask)
        self.task.tr = str
        self.task._app = None
        self.task.info = {}
        self.task.goals = []
        self.task.config = {'Ascension Materials': True, 'Skill Materials': True}
        self.task._combat_deadline = 0
        self.task.logger = Mock()
        for name in ('next_frame', 'sleep', 'click', 'send_key', 'log_info', 'log_warning',
                     'combat_once', 'reset_combat_state', 'send_key_up', 'walk_to_treasure',
                     'pick_f', 'restart_challenge', 'make_sure_in_world',
                     'open_cultivation', 'enter_challenge'):
            setattr(self.task, name, Mock())
        self.task.pick_echo = Mock(return_value=True)
        self.task.ocr = Mock(return_value=[])
        self.task.wait_until = Mock(side_effect=lambda condition, **kwargs: condition())

    def prepare_farm(self, goals, inventories, claims, remaining):
        self.task.goals = goals
        self.task.claim_reward = Mock(side_effect=claims)
        self.task.read_reward_inventory = Mock(side_effect=inventories)
        self.task.read_remaining_stamina = Mock(side_effect=remaining)

    def prepare_claim(self, stamina=121, results=True):
        self.task.get_stamina = Mock(return_value=(stamina, 600, stamina + 600))
        self.task.has_claim_stamina = Mock(return_value=True)
        self.task.confirm_single_claim = Mock()
        self.task.ocr.return_value = [SimpleNamespace(name='退出副本'),
                                      SimpleNamespace(name='重新挑战')] if results else []

    def prepare_dialog(self, text=None):
        self.task.ocr.return_value = [SimpleNamespace(name=text)] if text else []
        self.task.click_dialog_left_button = Mock()
        self.task.click_dialog_right_button = Mock()

    def test_farm_does_not_restart_after_actual_inventory_meets_goal(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 29}], [181], [121])

        self.task.farm(181)

        self.task.combat_once.assert_called_once_with(wait_combat_time=30, target=True)
        self.task.claim_reward.assert_called_once_with()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(0, self.task.goals[0].missing)
        self.assertEqual(60, self.task.info['used stamina'])
        self.assertEqual('Cultivation materials meet the target', self.task.info['Stop Reason'])

    def test_farm_restarts_once_then_stops_with_insufficient_stamina(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 8}, {'材料': 12}], [121, 61], [61, 1])

        self.task.farm(121)

        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual(12, self.task.goals[0].owned)
        self.assertEqual(120, self.task.info['used stamina'])
        self.assertEqual('Waveplates below 60', self.task.info['Stop Reason'])

    def test_farm_continues_until_each_material_goal_is_complete(self):
        self.prepare_farm([MaterialGoal('材料甲', 27, 28, '共鸣者突破材料'),
                           MaterialGoal('材料乙', 5, 10, '共鸣者突破材料')],
                          [{'材料甲': 28, '材料乙': 8}, {'材料甲': 29, '材料乙': 10}],
                          [121, 61], [61, 1])

        self.task.farm(121)

        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual([0, 0], [goal.missing for goal in self.task.goals])
        self.assertEqual('Cultivation materials meet the target', self.task.info['Stop Reason'])

    def test_farm_stops_before_challenge_when_weekly_claims_are_zero(self):
        self.task.goals = [MaterialGoal('突破甲', 5, 5, '共鸣者突破材料'),
                           MaterialGoal('技能乙', 1, 5, '技能升级材料', 0)]
        self.task.claim_reward = Mock()

        self.task.farm(121)

        self.task.enter_challenge.assert_not_called()
        self.task.claim_reward.assert_not_called()
        self.assertEqual('Skill Materials have 0 weekly claims left', self.task.info['Stop Reason'])

    def test_farm_decrements_weekly_and_ends_row_when_exhausted(self):
        self.prepare_farm([MaterialGoal('技能乙', 1, 5, '技能升级材料', 1)],
                          [{'技能乙': 2}], [121], [61])

        self.task.farm(121)

        self.task.restart_challenge.assert_not_called()
        self.assertEqual(0, self.task.goals[0].weekly_left)
        self.assertEqual('Skill Materials have 0 weekly claims left', self.task.info['Stop Reason'])

    def test_two_failed_fights_stop_without_claiming_reward(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 8}], [121], [61])
        self.task.combat_once.side_effect = [NotInCombatException('first fight failed'),
                                             NotInCombatException('retry fight failed')]
        self.task.read_goals = Mock(return_value=[MaterialGoal('材料', 5, 28, '共鸣者突破材料')])
        self.task.read_current_stamina = Mock(return_value=121)

        with self.assertRaisesRegex(CultivationError, 'Challenge failed 2 times in a row'):
            self.task.farm(121)

        self.assertEqual(2, self.task.combat_once.call_count)
        self.task.claim_reward.assert_not_called()
        self.assertEqual(0, self.task._combat_deadline)

    def test_combat_timeout_stops_through_sleep_check(self):
        started = 100
        deadline = started + self.task.COMBAT_TIMEOUT

        def combat_once(**kwargs):
            self.task.sleep_check()
            self.task.sleep_check()

        self.task.combat_once.side_effect = combat_once
        with patch('src.task.CultivationTask.time.monotonic',
                   side_effect=[started, deadline - 1, deadline]), \
                patch.object(DomainTask, 'sleep_check'):
            with self.assertRaisesRegex(CultivationError, 'Combat exceeded 600 seconds'):
                self.task.fight()

        self.assertEqual(0, self.task._combat_deadline)

    def test_update_goals_rejects_inventory_regression(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, 'Reward inventory is lower than before the claim'):
            self.task.update_goals({'材料甲': 4, '材料乙': 3})

        self.assertEqual([5, 2], [goal.owned for goal in self.task.goals])

    def test_update_goals_accepts_partial_inventory(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28, '共鸣者突破材料'),
                           MaterialGoal('材料乙', 2, 10, '共鸣者突破材料')]

        self.task.update_goals({'材料甲': 8})

        self.assertEqual([8, 2], [goal.owned for goal in self.task.goals])

    def test_update_goals_rejects_unknown_material(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28, '共鸣者突破材料')]

        with self.assertRaisesRegex(CultivationError, 'Unknown material in the reward inventory'):
            self.task.update_goals({'材料乙': 9})

    def test_update_goals_rejects_no_progress(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, 'Target materials did not increase after the claim'):
            self.task.update_goals({'材料甲': 5, '材料乙': 2})

    def test_claim_reward_confirms_single_claim_once(self):
        self.prepare_claim()
        self.task.has_claim_stamina = Mock(side_effect=[False, True, True])

        self.assertEqual(121, self.task.claim_reward())

        self.task.confirm_single_claim.assert_called_once_with()
        self.task.walk_to_treasure.assert_called_once_with()

    def test_claim_reward_stops_after_two_failed_relocations(self):
        self.prepare_claim()
        self.task.has_claim_stamina.return_value = False

        with self.assertRaisesRegex(CultivationError, 'Claim dialog did not open'):
            self.task.claim_reward()

        self.assertEqual([call(), call()], self.task.walk_to_treasure.call_args_list)
        self.task.confirm_single_claim.assert_not_called()

    def test_claim_reward_does_not_claim_when_insufficient(self):
        self.prepare_claim(stamina=59)

        with self.assertRaisesRegex(CultivationError, 'Waveplates below 60'):
            self.task.claim_reward()

        self.task.confirm_single_claim.assert_not_called()
        self.task.send_key.assert_called_once_with('esc', after_sleep=0.5)

    def test_claim_reward_does_not_retry_after_result_timeout(self):
        self.prepare_claim(results=False)

        with self.assertRaisesRegex(CultivationError, 'Claim result not confirmed'):
            self.task.claim_reward()

        self.task.confirm_single_claim.assert_called_once_with()
        self.task.walk_to_treasure.assert_not_called()

    def test_confirm_single_claim_picks_button_by_dialog(self):
        for text, left, right in ((None, 1, 0),
                                  ('领取奖励需消耗60点结晶波片，请确认是否领取?', 0, 1)):
            with self.subTest(text=text):
                self.prepare_dialog(text)

                self.task.confirm_single_claim()

                self.assertEqual(left, self.task.click_dialog_left_button.call_count)
                self.assertEqual(right, self.task.click_dialog_right_button.call_count)

    def test_confirm_single_claim_rejects_unexpected_cost_without_clicking(self):
        self.prepare_dialog('领取奖励需消耗40点结晶波片，请确认是否领取?')

        with self.assertRaisesRegex(CultivationError, 'Claim costs 40 Waveplates'):
            self.task.confirm_single_claim()

        self.task.click_dialog_left_button.assert_not_called()
        self.task.click_dialog_right_button.assert_not_called()

    def test_has_claim_stamina_accepts_text_when_feature_is_missing(self):
        self.task.in_team = Mock(return_value=(False, None))
        self.task.find_one = Mock(return_value=None)
        self.task.ocr.return_value = [
            SimpleNamespace(name='领取奖励需消耗60点结晶波片，请确认是否领取?')]

        self.assertIs(True, self.task.has_claim_stamina())

    def test_enter_challenge_rejects_missing_material_row(self):
        self.task.read_target_row = Mock(return_value=None)

        with self.assertRaisesRegex(CultivationError, 'Ascension Materials row is missing'):
            CultivationTask.enter_challenge(self.task, '共鸣者突破材料')

        self.task.click.assert_not_called()

    def test_read_goals_skips_disabled_material_row(self):
        self.task.config['Skill Materials'] = False
        rows = {'共鸣者突破材料': MaterialRow(
            '共鸣者突破材料', 0.32, [(Box(1460, 369, 56, 24), (3, 46))])}
        self.task.read_target_row = Mock(side_effect=lambda material_type: rows[material_type])
        self.task.read_item_detail = Mock(return_value=('甲', 3))

        goals = self.task.read_goals()

        self.assertEqual(['甲'], [goal.name for goal in goals])
        self.task.read_target_row.assert_called_with('共鸣者突破材料')

    def test_read_goals_stops_when_weekly_count_is_missing(self):
        rows = {
            '共鸣者突破材料': MaterialRow(
                '共鸣者突破材料', 0.32, [(Box(1460, 369, 56, 24), (3, 46))]),
            '技能升级材料': MaterialRow(
                '技能升级材料', 0.58, [(Box(1464, 669, 47, 21), (4, 26))], None),
        }
        self.task.read_target_row = Mock(side_effect=lambda material_type: rows[material_type])
        self.task.read_item_detail = Mock()

        with self.assertRaisesRegex(CultivationError, 'Weekly claims left for Skill Materials not recognized'):
            self.task.read_goals()

        self.task.read_item_detail.assert_not_called()

    def test_read_reward_inventory_rejects_other_material(self):
        self.task.goals = [MaterialGoal('甲', 0, 5, '共鸣者突破材料')]
        self.task.ocr = Mock(return_value=[
            Box(100 + index * 170, 500, 80, 40, name='×1') for index in range(6)])
        self.task.read_item_detail = Mock(return_value=('乙', 9))

        with self.assertRaisesRegex(CultivationError, 'not a target material'):
            CultivationTask.read_reward_inventory(self.task, '共鸣者突破材料')


if __name__ == '__main__':
    unittest.main()
