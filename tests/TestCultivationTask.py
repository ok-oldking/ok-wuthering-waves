import unittest
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, call, patch

from ok import Box, CannotFindException, WaitFailedException
from src.task.BaseCombatTask import NotInCombatException
from src.task.BaseWWTask import BaseWWTask
from src.task.CultivationTask import CultivationError, CultivationTask, MaterialGoal, MaterialRow, parse_quantity
from src.task.DomainTask import DomainTask


class TestCultivationTask(unittest.TestCase):

    def setUp(self):
        self.task = CultivationTask.__new__(CultivationTask)
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
        self.task.use_stamina = Mock(return_value=(True, 60))
        self.task.ocr.return_value = [SimpleNamespace(name='退出副本'),
                                      SimpleNamespace(name='重新挑战')] if results else []

    def prepare_enter_challenge(self, material_type='共鸣者突破材料'):
        row_box = Box(1460, 369, 56, 24, name='3/46')
        self.task.read_target_row = Mock(
            return_value=MaterialRow(material_type, 0.32, [(row_box, (3, 46))]))
        self.task.wait_feature = Mock(return_value=True)
        self.task.click_team_challenge = Mock()
        self.task.wait_in_team_and_world = Mock()
        self.task.teleport_timeout = 100
        height = patch.object(CultivationTask, 'height', new_callable=PropertyMock,
                              return_value=1080)
        width = patch.object(CultivationTask, 'width', new_callable=PropertyMock,
                             return_value=1920)
        height.start()
        width.start()
        self.addCleanup(height.stop)
        self.addCleanup(width.stop)

    def test_parse_quantity_accepts_zero_exact_and_excess_owned(self):
        for text, expected in (('0/28', (0, 28)), ('28/28', (28, 28)),
                               ('29/28', (29, 28)), ('２８ ／ ２８', (28, 28)),
                               (' \t０ / ２８\n', (0, 28))):
            with self.subTest(text=text):
                self.assertEqual(expected, parse_quantity(text))

    def test_parse_quantity_rejects_zero_required_garbage_and_multiple_fractions(self):
        for text in ('0/0', '28/0', '垃圾文本', '', '0/28 28/28', '0/28/28'):
            with self.subTest(text=text):
                self.assertIsNone(parse_quantity(text))

    def test_material_goal_missing_stops_at_zero(self):
        for owned, missing in ((0, 28), (5, 23), (28, 0), (29, 0)):
            with self.subTest(owned=owned):
                self.assertEqual(missing, MaterialGoal('材料', owned, 28).missing)

    def test_read_stable_returns_after_two_matching_reads(self):
        reader = Mock(side_effect=[(5, 28), (5, 28)])

        self.assertEqual((5, 28), self.task.read_stable(reader, '库存'))

        self.assertEqual(2, reader.call_count)
        self.assertEqual(2, self.task.next_frame.call_count)
        self.task.sleep.assert_called_once_with(0.3)

    def test_read_stable_rejects_three_missing_reads(self):
        reader = Mock(return_value=None)

        with self.assertRaisesRegex(CultivationError, '库存识别失败'):
            self.task.read_stable(reader, '库存')

        self.assertEqual(3, reader.call_count)
        self.assertEqual(3, self.task.next_frame.call_count)
        self.assertEqual([call(0.3)] * 3, self.task.sleep.call_args_list)

    def test_read_stable_rejects_three_fluctuating_reads(self):
        reader = Mock(side_effect=[5, 8, 5])

        with self.assertRaisesRegex(CultivationError, '库存识别失败'):
            self.task.read_stable(reader, '库存')

        self.assertEqual(3, reader.call_count)
        self.assertEqual(3, self.task.next_frame.call_count)

    def test_read_stable_accepts_zero(self):
        reader = Mock(side_effect=[0, 0])

        self.assertEqual(0, self.task.read_stable(reader, '库存'))

        self.assertEqual(2, reader.call_count)

    def test_enter_challenge_clicks_ascension_button_by_fixed_position(self):
        self.prepare_enter_challenge()

        CultivationTask.enter_challenge(self.task, '共鸣者突破材料')

        self.task.click.assert_called_once_with(0.900, 0.320, after_sleep=1)
        self.task.wait_feature.assert_called_once_with(
            'team_start_challenge', time_out=10, raise_if_not_found=False)
        self.task.click_team_challenge.assert_called_once_with()
        self.task.wait_in_team_and_world.assert_called_once_with(time_out=100)
        self.task.read_target_row.assert_called_once_with('共鸣者突破材料')

    def test_enter_challenge_clicks_skill_button_and_solo_by_fixed_position(self):
        self.prepare_enter_challenge()
        self.task.wait_feature.side_effect = [None, True]

        CultivationTask.enter_challenge(self.task, '技能升级材料')

        self.assertEqual([call(0.900, 0.597, after_sleep=1),
                          call(0.800, 0.910, after_sleep=1)],
                         self.task.click.call_args_list)
        self.assertEqual([call('team_start_challenge', time_out=10, raise_if_not_found=False),
                          call('team_start_challenge', time_out=20, raise_if_not_found=False)],
                         self.task.wait_feature.call_args_list)
        self.task.click_team_challenge.assert_called_once_with()
        self.task.wait_in_team_and_world.assert_called_once_with(time_out=100)

    def test_enter_challenge_rejects_missing_material_row(self):
        self.prepare_enter_challenge()
        self.task.read_target_row.return_value = None

        with self.assertRaisesRegex(CultivationError, '共鸣者突破材料行已消失'):
            CultivationTask.enter_challenge(self.task, '共鸣者突破材料')

        self.task.ocr.assert_not_called()
        self.task.click.assert_not_called()
        self.task.wait_feature.assert_not_called()
        self.task.click_team_challenge.assert_not_called()
        self.task.wait_in_team_and_world.assert_not_called()

    def test_enter_challenge_stops_when_team_page_is_missing(self):
        self.prepare_enter_challenge()
        self.task.wait_feature.return_value = None

        with self.assertRaisesRegex(CultivationError, '未进入编队页'):
            CultivationTask.enter_challenge(self.task, '共鸣者突破材料')

        self.assertEqual([call(0.900, 0.320, after_sleep=1),
                          call(0.800, 0.910, after_sleep=1)],
                         self.task.click.call_args_list)
        self.assertEqual([call('team_start_challenge', time_out=10, raise_if_not_found=False),
                          call('team_start_challenge', time_out=20, raise_if_not_found=False)],
                         self.task.wait_feature.call_args_list)
        self.task.click_team_challenge.assert_not_called()
        self.task.wait_in_team_and_world.assert_not_called()

    def test_farm_does_not_restart_after_actual_inventory_meets_goal(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 29}], [(181, 60)], [121])

        self.task.farm(181)

        self.task.combat_once.assert_called_once_with(wait_combat_time=30, target=True)
        self.task.claim_reward.assert_called_once_with()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(29, self.task.goals[0].owned)
        self.assertEqual(0, self.task.goals[0].missing)
        self.assertEqual('29/28，已满足', self.task.info['材料'])
        self.assertEqual(60, self.task.info['used stamina'])
        self.assertEqual('培养材料已满足需求', self.task.info['停止原因'])

    def test_farm_restarts_once_then_stops_with_insufficient_stamina(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 8}, {'材料': 12}], [(121, 60), (61, 60)], [61, 1])
        states = []
        self.task.restart_challenge.side_effect = lambda: states.append(
            (self.task.goals[0].owned, self.task.goals[0].missing))

        self.task.farm(121)

        self.assertEqual([(8, 20)], states)
        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.combat_once.call_count)
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual(12, self.task.goals[0].owned)
        self.assertEqual(16, self.task.goals[0].missing)
        self.assertEqual(120, self.task.info['used stamina'])
        self.assertEqual('当前结晶波片不足 60 点', self.task.info['停止原因'])

    def test_farm_stops_when_remaining_stamina_is_below_sixty(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 8}], [(119, 60)], [59])

        self.task.farm(119)

        self.task.claim_reward.assert_called_once_with()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(8, self.task.goals[0].owned)
        self.assertEqual('当前结晶波片不足 60 点', self.task.info['停止原因'])

    def test_farm_continues_until_each_material_goal_is_complete(self):
        self.prepare_farm([MaterialGoal('材料甲', 27, 28, '共鸣者突破材料'),
                           MaterialGoal('材料乙', 5, 10, '共鸣者突破材料')],
                          [{'材料甲': 28, '材料乙': 8}, {'材料甲': 29, '材料乙': 10}],
                          [(121, 60), (61, 60)], [61, 1])
        states = []
        self.task.restart_challenge.side_effect = lambda: states.append(self.task.info.copy())

        self.task.farm(121)

        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual('28/28，已满足', states[0]['材料甲'])
        self.assertEqual('8/10，缺少 2 个', states[0]['材料乙'])
        self.assertNotIn('停止原因', states[0])
        self.assertEqual([29, 10], [goal.owned for goal in self.task.goals])
        self.assertEqual([0, 0], [goal.missing for goal in self.task.goals])
        self.assertEqual('29/28，已满足', self.task.info['材料甲'])
        self.assertEqual('10/10，已满足', self.task.info['材料乙'])
        self.assertEqual('培养材料已满足需求', self.task.info['停止原因'])

    def test_update_goals_rejects_inventory_regression(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, '奖励库存小于领取前库存'):
            self.task.update_goals({'材料甲': 4, '材料乙': 3})

        self.assertEqual([5, 2], [goal.owned for goal in self.task.goals])
        self.assertEqual({}, self.task.info)

    def test_update_goals_accepts_partial_inventory(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28, '共鸣者突破材料'),
                           MaterialGoal('材料乙', 2, 10, '共鸣者突破材料')]

        self.task.update_goals({'材料甲': 8})

        self.assertEqual([8, 2], [goal.owned for goal in self.task.goals])
        self.assertEqual('8/28，缺少 20 个', self.task.info['材料甲'])
        self.assertEqual('2/10，缺少 8 个', self.task.info['材料乙'])

    def test_update_goals_rejects_unknown_material(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28, '共鸣者突破材料')]

        with self.assertRaisesRegex(CultivationError, '奖励库存出现未知材料'):
            self.task.update_goals({'材料乙': 9})

    def test_update_goals_rejects_no_progress(self):
        self.task.goals = [MaterialGoal('材料甲', 5, 28), MaterialGoal('材料乙', 2, 10)]

        with self.assertRaisesRegex(CultivationError, '领取后目标材料未增加'):
            self.task.update_goals({'材料甲': 5, '材料乙': 2})

        self.assertEqual([5, 2], [goal.owned for goal in self.task.goals])
        self.assertEqual({}, self.task.info)

    def test_claim_reward_uses_stamina_once_with_force_single(self):
        self.prepare_claim()
        self.task.has_claim_stamina.side_effect = [False, True, True]

        self.assertEqual((121, 60), self.task.claim_reward())

        self.task.use_stamina.assert_called_once_with(once=60, force_single=True)
        self.task.walk_to_treasure.assert_called_once_with()
        self.task.pick_f.assert_called_once_with(handle_claim=False)
        self.task.click.assert_not_called()
        self.assertEqual(121, self.task.info['current_stamina'])

    def test_claim_reward_relocates_twice_before_using_stamina_once(self):
        self.prepare_claim()
        self.task.has_claim_stamina.side_effect = [False, False, False, True, True]

        self.assertEqual((121, 60), self.task.claim_reward())

        self.assertEqual([call(), call()], self.task.walk_to_treasure.call_args_list)
        self.assertEqual([call(handle_claim=False)] * 2, self.task.pick_f.call_args_list)
        self.task.use_stamina.assert_called_once_with(once=60, force_single=True)

    def test_claim_reward_stops_after_two_failed_relocations(self):
        self.prepare_claim()
        self.task.has_claim_stamina.return_value = False

        with self.assertRaisesRegex(CultivationError, '未打开领取奖励确认框'):
            self.task.claim_reward()

        self.assertEqual([call(), call()], self.task.walk_to_treasure.call_args_list)
        self.assertEqual([call(handle_claim=False)] * 2, self.task.pick_f.call_args_list)
        self.task.use_stamina.assert_not_called()

    def test_claim_reward_reports_missing_treasure(self):
        self.prepare_claim()
        self.task.has_claim_stamina.return_value = False
        self.task.walk_to_treasure.side_effect = WaitFailedException()

        with self.assertRaisesRegex(CultivationError, '未找到奖励箱'):
            self.task.claim_reward()

        self.task.walk_to_treasure.assert_called_once_with()
        self.task.use_stamina.assert_not_called()

    def test_claim_reward_does_not_use_stamina_when_insufficient(self):
        self.prepare_claim(stamina=59)

        with self.assertRaisesRegex(CultivationError, '当前结晶波片不足 60 点'):
            self.task.claim_reward()

        self.task.use_stamina.assert_not_called()
        self.task.walk_to_treasure.assert_not_called()
        self.task.click.assert_not_called()
        self.task.send_key.assert_called_once_with('esc', after_sleep=0.5)

    def test_claim_reward_does_not_retry_after_result_timeout(self):
        self.prepare_claim(results=False)

        with self.assertRaisesRegex(CultivationError, '未确认奖励领取结果'):
            self.task.claim_reward()

        self.task.use_stamina.assert_called_once_with(once=60, force_single=True)
        self.task.walk_to_treasure.assert_not_called()
        self.task.click.assert_not_called()
        self.assertEqual(15, self.task.wait_until.call_args.kwargs['time_out'])

    def test_claim_reward_does_not_retry_after_helper_error(self):
        self.prepare_claim()
        error = RuntimeError('claim helper failed')
        self.task.use_stamina.side_effect = error

        with self.assertRaises(RuntimeError) as raised:
            self.task.claim_reward()

        self.assertIs(error, raised.exception)
        self.task.use_stamina.assert_called_once_with(once=60, force_single=True)
        self.task.walk_to_treasure.assert_not_called()
        self.task.click.assert_not_called()
        self.task.ocr.assert_not_called()

    def test_use_stamina_force_single_uses_left_button_and_sixty(self):
        self.task.get_stamina = Mock(return_value=(180, 0, 180))
        self.task.wait_feature = Mock(return_value=None)
        self.task.click_dialog_left_button = Mock()
        self.task.click_dialog_right_button = Mock()

        self.assertEqual((True, 60), BaseWWTask.use_stamina(self.task, once=60, force_single=True))

        self.task.click_dialog_left_button.assert_called_once_with()
        self.task.click_dialog_right_button.assert_not_called()
        self.task.click.assert_not_called()

    def test_use_stamina_defaults_to_right_button_and_double_cost(self):
        self.task.get_stamina = Mock(return_value=(180, 0, 180))
        self.task.wait_feature = Mock(return_value=None)
        self.task.click_dialog_left_button = Mock()
        self.task.click_dialog_right_button = Mock()

        self.assertEqual((True, 120), BaseWWTask.use_stamina(self.task, once=60))

        self.task.click_dialog_right_button.assert_called_once_with()
        self.task.click_dialog_left_button.assert_not_called()
        self.task.click.assert_not_called()

    def test_use_stamina_text_claim_uses_right_button_and_sixty(self):
        self.task.get_stamina = Mock(return_value=(180, 0, 180))
        self.task.ocr.return_value = [
            SimpleNamespace(name='领取奖励需消耗60点结晶波片，请确认是否领取?')]
        self.task.wait_feature = Mock(return_value=None)
        self.task.click_dialog_left_button = Mock()
        self.task.click_dialog_right_button = Mock()

        self.assertEqual((True, 60), BaseWWTask.use_stamina(self.task, once=60, force_single=True))

        self.task.click_dialog_right_button.assert_called_once_with()
        self.task.click_dialog_left_button.assert_not_called()
        self.task.click.assert_not_called()

    def test_use_stamina_text_claim_rejects_unexpected_cost_without_clicking(self):
        self.task.get_stamina = Mock(return_value=(180, 0, 180))
        self.task.ocr.return_value = [
            SimpleNamespace(name='领取奖励需消耗40点结晶波片，请确认是否领取?')]
        self.task.wait_feature = Mock(return_value=None)
        self.task.click_dialog_left_button = Mock()
        self.task.click_dialog_right_button = Mock()

        with self.assertRaisesRegex(CannotFindException, '奖励消耗为 40 点'):
            BaseWWTask.use_stamina(self.task, once=60, force_single=True)

        self.task.click_dialog_left_button.assert_not_called()
        self.task.click_dialog_right_button.assert_not_called()
        self.task.click.assert_not_called()

    def test_has_claim_stamina_accepts_text_when_feature_is_missing(self):
        self.task.in_team = Mock(return_value=(False, None))
        self.task.find_one = Mock(return_value=None)
        self.task.ocr.return_value = [
            SimpleNamespace(name='领取奖励需消耗60点结晶波片，请确认是否领取?')]

        self.assertIs(BaseWWTask.has_claim_stamina(self.task), True)

        self.task.find_one.assert_called_once_with('claim_stamina_sign')

    def test_two_failed_fights_stop_without_claiming_reward(self):
        self.prepare_farm([MaterialGoal('材料', 5, 28, '共鸣者突破材料')],
                          [{'材料': 8}], [(121, 60)], [61])
        self.task.combat_once.side_effect = [NotInCombatException('first fight failed'),
                                             NotInCombatException('retry fight failed')]
        self.task.read_goals = Mock(return_value=[MaterialGoal('材料', 5, 28, '共鸣者突破材料')])
        self.task.read_current_stamina = Mock(return_value=121)

        with self.assertRaisesRegex(CultivationError, '挑战连续失败 2 次'):
            self.task.farm(121)

        self.assertEqual(2, self.task.combat_once.call_count)
        self.assertEqual(2, self.task.reset_combat_state.call_count)
        self.assertEqual([call('共鸣者突破材料'), call('共鸣者突破材料')],
                         self.task.enter_challenge.call_args_list)
        self.task.claim_reward.assert_not_called()
        self.task.read_reward_inventory.assert_not_called()
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(5, self.task.goals[0].owned)
        self.assertEqual(0, self.task._combat_deadline)

    def test_combat_timeout_stops_through_sleep_check(self):
        started = 100
        deadline = started + self.task.COMBAT_TIMEOUT

        def combat_once(**kwargs):
            self.assertEqual(deadline, self.task._combat_deadline)
            self.task.sleep_check()
            self.task.sleep_check()

        self.task.combat_once.side_effect = combat_once
        with patch('src.task.CultivationTask.time.monotonic',
                   side_effect=[started, deadline - 1, deadline]), \
                patch.object(DomainTask, 'sleep_check') as parent_sleep_check:
            with self.assertRaisesRegex(CultivationError, '战斗超过 600 秒'):
                self.task.fight()
            parent_sleep_check.assert_called_once_with()

        self.task.combat_once.assert_called_once_with(wait_combat_time=30, target=True)
        self.task.reset_combat_state.assert_called_once_with('cultivation combat ended')
        self.assertEqual(0, self.task._combat_deadline)

    def test_read_target_row_parses_weekly_count_and_quantities(self):
        height = patch.object(CultivationTask, 'height', new_callable=PropertyMock,
                              return_value=1080)
        width = patch.object(CultivationTask, 'width', new_callable=PropertyMock,
                             return_value=1920)
        height.start()
        width.start()
        self.addCleanup(height.stop)
        self.addCleanup(width.stop)
        label = Box(762, 609, 164, 33, name='技能升级材料')
        weekly = Box(761, 647, 304, 35, name='本周剩余可收取次数：3/3')
        right = Box(1464, 669, 47, 21, name='2/26')
        left = Box(1300, 669, 52, 21, name='1/12')
        self.task.ocr.side_effect = lambda x, y, to_x, to_y, **kwargs: (
            [label] if y == 0.18 else [weekly, right, left])

        row = CultivationTask.read_target_row(self.task, '技能升级材料')

        self.assertEqual('技能升级材料', row.material_type)
        self.assertAlmostEqual(0.580, row.y, places=3)
        self.assertEqual([(left, (1, 12)), (right, (2, 26))], row.quantities)
        self.assertEqual(3, row.weekly_left)

    def test_enabled_materials_follows_switches(self):
        self.assertEqual(['共鸣者突破材料', '技能升级材料'], self.task.enabled_materials())

        self.task.config['Ascension Materials'] = False
        self.assertEqual(['技能升级材料'], self.task.enabled_materials())

        self.task.config['Skill Materials'] = False
        self.assertEqual([], self.task.enabled_materials())

    def test_read_goals_skips_disabled_material_row(self):
        self.task.config['Skill Materials'] = False
        rows = {'共鸣者突破材料': MaterialRow(
            '共鸣者突破材料', 0.32, [(Box(1460, 369, 56, 24), (3, 46))])}
        self.task.read_target_row = Mock(side_effect=lambda material_type: rows[material_type])
        self.task.read_item_detail = Mock(return_value=('甲', 3))

        goals = self.task.read_goals()

        self.assertEqual(['甲'], [goal.name for goal in goals])
        self.task.read_target_row.assert_called_with('共鸣者突破材料')
        self.task.read_item_detail.assert_called_with(('共鸣者突破材料',))

    def test_read_goals_reads_both_material_rows(self):
        rows = {
            '共鸣者突破材料': MaterialRow(
                '共鸣者突破材料', 0.32, [(Box(1460, 369, 56, 24), (3, 46))]),
            '技能升级材料': MaterialRow(
                '技能升级材料', 0.58, [(Box(1464, 669, 47, 21), (4, 26))], 2),
        }
        self.task.read_target_row = Mock(side_effect=lambda material_type: rows[material_type])
        self.task.read_item_detail = Mock(side_effect=lambda types: (
            ('甲', 3) if types == ('共鸣者突破材料',) else ('乙', 4)))

        goals = self.task.read_goals()

        self.assertEqual(['甲', '乙'], [goal.name for goal in goals])
        self.assertEqual(['共鸣者突破材料', '技能升级材料'],
                         [goal.material_type for goal in goals])
        self.assertEqual([None, 2], [goal.weekly_left for goal in goals])
        self.assertEqual([3, 4], [goal.owned for goal in goals])
        self.assertEqual([46, 26], [goal.required for goal in goals])
        self.assertEqual('3/46，缺少 43 个', self.task.info['甲'])
        self.assertEqual('4/26，缺少 22 个，本周剩余 2 次', self.task.info['乙'])

    def test_read_goals_stops_when_weekly_count_is_missing(self):
        rows = {
            '共鸣者突破材料': MaterialRow(
                '共鸣者突破材料', 0.32, [(Box(1460, 369, 56, 24), (3, 46))]),
            '技能升级材料': MaterialRow(
                '技能升级材料', 0.58, [(Box(1464, 669, 47, 21), (4, 26))], None),
        }
        self.task.read_target_row = Mock(side_effect=lambda material_type: rows[material_type])
        self.task.read_item_detail = Mock()

        with self.assertRaisesRegex(CultivationError, '未识别技能升级材料本周剩余次数'):
            self.task.read_goals()

        self.task.read_item_detail.assert_not_called()

    def test_farm_stops_before_challenge_when_weekly_claims_are_zero(self):
        self.task.goals = [MaterialGoal('突破甲', 5, 5, '共鸣者突破材料'),
                           MaterialGoal('技能乙', 1, 5, '技能升级材料', 0)]
        self.task.claim_reward = Mock()
        self.task.read_reward_inventory = Mock()

        self.task.farm(121)

        self.task.enter_challenge.assert_not_called()
        self.task.claim_reward.assert_not_called()
        self.assertEqual('技能升级材料本周剩余收取次数为 0', self.task.info['停止原因'])

    def test_farm_decrements_weekly_and_ends_row_when_exhausted(self):
        self.prepare_farm([MaterialGoal('技能乙', 1, 5, '技能升级材料', 1)],
                          [{'技能乙': 2}], [(121, 60)], [61])

        self.task.farm(121)

        self.task.enter_challenge.assert_called_once_with('技能升级材料')
        self.task.read_reward_inventory.assert_called_once_with('技能升级材料')
        self.task.restart_challenge.assert_not_called()
        self.assertEqual(0, self.task.goals[0].weekly_left)
        self.assertEqual('2/5，缺少 3 个，本周剩余 0 次', self.task.info['技能乙'])
        self.assertEqual(60, self.task.info['used stamina'])
        self.assertEqual('技能升级材料本周剩余收取次数为 0', self.task.info['停止原因'])

    def test_farm_consumes_one_weekly_claim_per_reward_and_restarts(self):
        self.prepare_farm([MaterialGoal('技能乙', 1, 9, '技能升级材料', 2)],
                          [{'技能乙': 2}, {'技能乙': 3}], [(121, 60), (61, 60)], [61, 1])

        self.task.farm(121)

        self.task.restart_challenge.assert_called_once_with()
        self.assertEqual(2, self.task.claim_reward.call_count)
        self.assertEqual(0, self.task.goals[0].weekly_left)
        self.assertEqual(120, self.task.info['used stamina'])
        self.assertEqual('当前结晶波片不足 60 点', self.task.info['停止原因'])

    def test_read_reward_inventory_clicks_fifth_slot_of_six(self):
        self.task.goals = [MaterialGoal('甲', 0, 5, '共鸣者突破材料'),
                           MaterialGoal('乙', 0, 5, '技能升级材料', 3)]
        self.set_reward_slots(6)
        self.task.read_item_detail = Mock(side_effect=[('甲', 3), ('甲', 3), ('甲', 3)])

        inventory = CultivationTask.read_reward_inventory(self.task, '共鸣者突破材料')

        self.assertEqual({'甲': 3}, inventory)
        self.assertEqual([call(self.slot_x(4, 6), CultivationTask.REWARD_SLOT_Y,
                               name='奖励槽5', after_sleep=0.4),
                          call(0.5, 0.94, after_sleep=0.3)],
                         self.task.click.call_args_list)
        self.task.read_item_detail.assert_any_call(('共鸣者突破材料', '技能升级材料'))

    def test_read_reward_inventory_clicks_fifth_slot_of_seven(self):
        self.task.goals = [MaterialGoal('甲', 0, 5, '共鸣者突破材料')]
        self.set_reward_slots(7)
        self.task.read_item_detail = Mock(side_effect=[('甲', 3), ('甲', 3), ('甲', 3)])

        CultivationTask.read_reward_inventory(self.task, '共鸣者突破材料')

        self.assertEqual(call(self.slot_x(4, 7), CultivationTask.REWARD_SLOT_Y,
                              name='奖励槽5', after_sleep=0.4),
                         self.task.click.call_args_list[0])

    def test_read_reward_inventory_rejects_other_material_in_fifth_slot(self):
        self.task.goals = [MaterialGoal('甲', 0, 5, '共鸣者突破材料')]
        self.set_reward_slots(6)
        self.task.read_item_detail = Mock(side_effect=[('乙', 9), ('乙', 9), ('乙', 9)])

        with self.assertRaisesRegex(CultivationError, '不是目标材料'):
            CultivationTask.read_reward_inventory(self.task, '共鸣者突破材料')

        self.assertEqual(2, self.task.click.call_count)

    def set_reward_slots(self, count):
        self.task.ocr = Mock(return_value=[
            Box(100 + index * 170, 500, 80, 40, name='×1') for index in range(count)])

    @staticmethod
    def slot_x(index, count):
        return 0.5 + (index - (count - 1) / 2) * CultivationTask.REWARD_SLOT_SPACING

    def test_collect_optional_echo_uses_nest_search_before_claim(self):
        self.task.pick_echo = Mock(return_value=False)
        self.task.walk_find_echo = Mock(return_value=True)
        self.task.yolo_find_echo = Mock()

        CultivationTask.collect_optional_echo(self.task)

        self.task.walk_find_echo.assert_called_once_with(time_out=5, backward_time=2.5)
        self.task.yolo_find_echo.assert_not_called()

    def test_collect_optional_echo_falls_back_to_yolo_search(self):
        self.task.pick_echo = Mock(return_value=False)
        self.task.walk_find_echo = Mock(return_value=None)
        self.task.yolo_find_echo = Mock(return_value=(False, False))

        CultivationTask.collect_optional_echo(self.task)

        self.task.yolo_find_echo.assert_called_once_with(
            turn=True, use_color=False, time_out=30)
        self.task.send_key_up.assert_any_call('w')


if __name__ == '__main__':
    unittest.main()
