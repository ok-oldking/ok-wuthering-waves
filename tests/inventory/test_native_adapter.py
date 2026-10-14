from src.task import InventoryMaintain as stock
from src.inventory_support import native_control as natural
from src.inventory_support import native_control as stamina
control = natural
ROOT = stock.ROOT
'Native farming adapter boundary tests; fake frames and no game/resources spent.'
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
base = ModuleType('src.task.WWOneTimeTask')
base.WWOneTimeTask = SimpleNamespace(run=lambda child: None)
simulation = ModuleType('src.task.SimulationTask')
simulation.SimulationTask = type('SimulationTask', (), {})
forgery = ModuleType('src.task.ForgeryTask')
forgery.ForgeryTask = type('ForgeryTask', (), {})
modules = {'src.inventory_support.native_control': control, 'src.task.NaturalStamina': natural, 'src.task.StaminaPlan': stamina, 'src.task.WWOneTimeTask': base, 'src.task.SimulationTask': simulation, 'src.task.ForgeryTask': forgery}

class SavedConfig(dict):

    def __init__(self, path, values):
        super().__init__(values)
        self.config_file, self.fail = (path, False)
        path.write_text(json.dumps(values), encoding='utf-8')

    def __setitem__(self, key, value):
        super().__setitem__(key, deepcopy(value))
        if not self.fail:
            self.config_file.write_text(json.dumps(self), encoding='utf-8')

class Child:
    stamina_once = 40

    def __init__(self):
        self.config = {'Material Selection': 'Shell Credit'}
        self.current, self.claims, self.valid_claim = (240, 0, True)
        self.expected_selection = 'Resonator EXP'
        self.sleep = self.back = self.ensure_main = self.openF2Book = self.make_sure_in_world = lambda *a, **k: None

    def get_stamina(self):
        return (self.current, 999, self.current + 999)

    def wait_ocr(self, *a, **k):
        return [SimpleNamespace(name=f'{self.current}/240')]

    def in_combat(self):
        return True

    def has_claim_stamina(self):
        return self.valid_claim

    def click_dialog_left_button(self):
        self.current -= 40
        self.claims += 1

    def click_dialog_right_button(self):
        raise AssertionError('No double rewards')

    def wait_feature(self, *a, **k):
        return False

    def farm_simulation(self, *, daily, used_stamina, config):
        assert not daily and used_stamina == 0 and (config['Material Selection'] == self.expected_selection)
        can_continue, used = self.use_stamina(once=40)
        assert not can_continue and used == 40

class ForgeryChild(Child):
    total_number = 20
    structure = [5, 5, 5, 5]
    expected_index = 7
    filter_text = '武器类型/全部'

    def wait_ocr(self, left, *args, **kwargs):
        if left == 1840 / 2560:
            return [SimpleNamespace(name=self.filter_text)]
        return super().wait_ocr(left, *args, **kwargs)

    def click_on_book_target(self, serial, total, structure=None):
        self.selected_index = serial
        return True

    def farm_simulation(self, **kw):
        raise AssertionError('Forgery must not use simulation selection')

    def farm_forgery(self, *, daily, used_stamina, config):
        assert not daily and used_stamina == 0
        assert config['Which Forgery Challenge to Farm'] == self.expected_index
        self.click_on_book_target(self.expected_index, self.total_number, self.structure)
        self.forgery_calls = getattr(self, 'forgery_calls', 0) + 1
        can_continue, used = self.use_stamina(once=40)
        assert not can_continue and used == 40

class StockAdapterTests(unittest.TestCase):

    def setUp(self):
        waiting = patch.object(control, 'wait_seconds', return_value=None)
        waiting.start()
        self.addCleanup(waiting.stop)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.child = Child()
        self.parent = SimpleNamespace(config=SavedConfig(Path(self.temp.name) / 'config.json', {stock.PLAN_KEY: [], stock.PENDING_KEY: {}, 'Use Reserve Stamina to Finish Run': True}), _prepare_gameplay=Mock(), get_task_by_class=lambda cls: self.child, info_set=Mock(), log_info=Mock())
        self.rows = [dict(stock.material_options()[0], target=1)]
        seam = patch.object(stock, 'resolve_destination', side_effect=lambda child, parent, route, select: select(route['native_index'], 20, [5, 5, 5, 5]))
        seam.start()
        self.addCleanup(seam.stop)

    def pending(self):
        stock.store_value(self.parent, stock.PENDING_KEY, {'pending': True, 'cost': 40})

    def test_menu_only_calibrated_exact_routes_no_arbitrary_material(self):
        options = stock.material_options()
        self.assertEqual(len(options), 49)
        self.assertEqual([(row['id'], row['name'], row['route']) for row in options[4:8]], [('weapon-exp-basic', '初级能源核心', 'simulation-weapon-exp'), ('weapon-exp-medium', '中级能源核心', 'simulation-weapon-exp'), ('weapon-exp-advanced', '高级能源核心', 'simulation-weapon-exp'), ('weapon-exp-premium', '特级能源核心', 'simulation-weapon-exp')])
        self.assertEqual(stock.validate_targets(self.rows), self.rows)
        for key, value in (('name', 'wrong'), ('id', 'shell-credit'), ('route', 'simulation-shell-credit')):
            invalid = deepcopy(self.rows)
            invalid[0][key] = value
            with self.assertRaises(ValueError):
                stock.validate_targets(invalid)

    def test_disk_failure_cannot_authorize_claim_or_save(self):
        self.parent.config.fail = True
        with self.assertRaises(RuntimeError):
            self.pending()
        self.assertEqual(self.parent.config[stock.PENDING_KEY], {})
        self.assertEqual(self.child.claims, 0)

    def test_weapon_native_single40_claim_restores_original_settings(self):
        self.child.expected_selection = 'Weapon EXP'
        before = deepcopy(self.child.config)
        self.pending()
        with patch.dict('sys.modules', modules):
            stock.farm_once(self.parent, self.child, stock.ROUTES['simulation-weapon-exp'])
        self.assertEqual(self.child.claims, 1)
        self.assertEqual(self.child.current, 200)
        self.assertEqual(self.child.config, before)
        self.assertTrue(self.parent.config[stock.PENDING_KEY]['pending'])

    def test_weapon_full_cycle_refreshes_stock_before_completing(self):
        self.rows = [dict(next((r for r in stock.material_options() if r['id'] == 'weapon-exp-premium')), target=1)]
        self.child.expected_selection = 'Weapon EXP'
        self.test_full_cycle_fresh_inspections_priority_no_saved_child_changes()

    def test_only_reserve_number_is_unknown_not_zero_stamina(self):
        for texts in (['999'], [], ['0/240', '120/240'], ['2400/240'], ['-160/240'], ['60.5/240'], ['60/240.0']):
            self.child.wait_ocr = lambda *a, **k: [SimpleNamespace(name=text) for text in texts]
            with self.assertRaises(RuntimeError):
                stock.strict_current(self.child)
        self.child.wait_ocr = lambda *a, **k: [SimpleNamespace(name='0/240')]
        self.assertEqual(stock.strict_current(self.child), 0)

    def test_single40_claim_restores_native_config_and_methods(self):
        original = self.child.config
        self.pending()
        with patch.dict('sys.modules', modules):
            stock.farm_once(self.parent, self.child, stock.ROUTES['simulation-character-exp'])
        self.assertEqual(self.child.claims, 1)
        self.assertEqual(self.child.current, 200)
        self.assertIs(self.child.config, original)
        self.assertNotIn('get_stamina', self.child.__dict__)
        self.assertNotIn('use_stamina', self.child.__dict__)
        self.assertNotIn('in_combat', self.child.__dict__)
        self.assertTrue(self.parent.config[stock.PENDING_KEY]['pending'])

    def test_missing_claim_window_or_changed_disk_refuses_click(self):
        for disk in (False, True):
            self.pending()
            self.child.valid_claim = disk
            if disk:
                self.parent.config.config_file.write_text('{}')
            with patch.dict('sys.modules', modules), self.assertRaises(RuntimeError):
                stock.farm_once(self.parent, self.child, stock.ROUTES['simulation-character-exp'])
            self.assertEqual(self.child.claims, 0)
            self.assertEqual(self.child.config, {'Material Selection': 'Shell Credit'})

    def report(self):
        row = self.rows[0]
        now = datetime.now(timezone.utc).isoformat()
        equivalence = stock.policy(ROOT).equivalence
        siblings = equivalence.observation_rows(self.rows, equivalence.load_families(ROOT, 'wuwa'))
        return {'schema': 'inventory-report/v1', 'game': 'wuwa', 'materials': [dict(item, quantity=self.child.claims if item['id'] == row['id'] else 0, status='confirmed', evidence=[{'captured_at': now}] * 2) for item in siblings]}

    def test_full_cycle_fresh_inspections_priority_no_saved_child_changes(self):
        inspection = ModuleType('src.task.InventoryInspection')
        inspection.run_inventory_inspection = Mock(side_effect=lambda *a, **k: self.report())
        inspection.prepare = Mock()
        inspection.load_module = Mock()
        self.parent.config[stock.PLAN_KEY] = self.rows
        original = deepcopy(self.child.config)
        with patch.dict('sys.modules', dict(modules, **{'src.task.InventoryInspection': inspection})):
            result = stock.run_inventory_maintain(self.parent)
        self.assertEqual(result['state'], 'targets_met')
        self.assertEqual(inspection.run_inventory_inspection.call_count, 2)
        self.assertEqual(self.child.claims, 1)
        self.assertEqual(self.child.config, original)
        self.assertEqual(self.parent.config[stock.PENDING_KEY], {})
        self.assertEqual(self.parent.config[stock.HISTORY_KEY]['materials'][0]['quantity'], 1)

    def test_pending_restart_blocks_preparation_and_spending(self):
        self.parent.config[stock.PLAN_KEY] = self.rows
        self.pending()
        inspection = ModuleType('src.task.InventoryInspection')
        inspection.prepare = Mock()
        inspection.run_inventory_inspection = Mock()
        inspection.load_module = Mock()
        with patch.dict('sys.modules', dict(modules, **{'src.task.InventoryInspection': inspection})), self.assertRaises(RuntimeError):
            stock.run_inventory_maintain(self.parent)
        self.parent._prepare_gameplay.assert_not_called()
        inspection.prepare.assert_not_called()
        self.assertEqual(self.child.claims, 0)

    def forgery_route(self):
        return {'kind': 'Forgery', 'cost': 40, 'native_index': 7, 'name': 'synthetic', 'materials': ['synthetic-forgery-material']}

    def test_forgery_native_single_claim_restores_config_and_methods(self):
        child = ForgeryChild()
        original = child.config
        before = set(child.__dict__)
        self.pending()
        with patch.dict('sys.modules', modules):
            stock.farm_once(self.parent, child, self.forgery_route())
        self.assertEqual(child.claims, 1)
        self.assertEqual(child.forgery_calls, 1)
        self.assertEqual(child.current, 200)
        self.assertIs(child.config, original)
        self.assertEqual(set(child.__dict__) - before, {'forgery_calls', 'selected_index'})
        self.assertTrue(self.parent.config[stock.PENDING_KEY]['pending'])

    def test_route_types_indexes_and_costs_strict_before_input(self):
        for changes in ({'native_index': True}, {'native_index': 0}, {'native_index': 21}, {'native_index': '7'}, {'native_index': 7.5}, {'cost': True}, {'cost': 60}, {'kind': 'weekly'}, {'selection': 'Shell Credit'}):
            child = ForgeryChild()
            self.pending()
            route = dict(self.forgery_route(), **changes)
            with patch.dict('sys.modules', modules), self.assertRaises(ValueError):
                stock.farm_once(self.parent, child, route)
            self.assertEqual(child.claims, 0)
            self.assertNotIn('forgery_calls', child.__dict__)
            self.assertNotIn('get_stamina', child.__dict__)

    def test_missing_forgery_task_and_changed_upstream_structure_refused(self):
        self.parent.get_task_by_class = lambda cls: None
        with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, '未注册'):
            stock.native_child(self.parent, self.forgery_route())
        for total, structure in ((21, [5, 5, 5, 6]), (20, [10, 10])):
            child = ForgeryChild()
            child.total_number, child.structure = (total, structure)
            self.parent.get_task_by_class = lambda cls: child
            with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, '列表已改变'):
                stock.native_child(self.parent, self.forgery_route())
            self.pending()
            with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, '列表已改变'):
                stock.farm_once(self.parent, child, self.forgery_route())
            self.assertEqual(child.claims, 0)

    def test_each_route_resolves_its_registered_task_type(self):
        first, second = (Child(), ForgeryChild())
        self.parent.get_task_by_class = lambda cls: first if cls is simulation.SimulationTask else second if cls is forgery.ForgeryTask else None
        with patch.dict('sys.modules', modules):
            self.assertIs(stock.native_child(self.parent, stock.ROUTES['simulation-character-exp']), first)
            self.assertIs(stock.native_child(self.parent, self.forgery_route()), second)

    def test_forgery_missing_claim_or_persistence_failure_never_spends(self):
        for corrupt_disk in (False, True):
            self.pending()
            child = ForgeryChild()
            child.valid_claim = corrupt_disk
            if corrupt_disk:
                self.parent.config.config_file.write_text('{}')
            with patch.dict('sys.modules', modules), self.assertRaises(RuntimeError):
                stock.farm_once(self.parent, child, self.forgery_route())
            self.assertEqual(child.claims, 0)
            self.assertEqual(child.config, {'Material Selection': 'Shell Credit'})
            self.assertNotIn('get_stamina', child.__dict__)

    def test_forgery_failure_restores_native_config_and_claim_wrapper(self):
        child = ForgeryChild()
        original = child.config
        child.farm_forgery = Mock(side_effect=RuntimeError('native failure'))
        self.pending()
        with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, 'native failure'):
            stock.farm_once(self.parent, child, self.forgery_route())
        self.assertIs(child.config, original)
        self.assertNotIn('get_stamina', child.__dict__)
        self.assertNotIn('use_stamina', child.__dict__)
        self.assertNotIn('in_combat', child.__dict__)
        self.assertTrue(self.parent.config[stock.PENDING_KEY]['pending'])

    def test_only_measured_forgery_materials_are_offered(self):
        self.assertEqual({key: (route['native_index'], route['materials']) for key, route in stock.ROUTES.items() if route.get('kind') == 'Forgery' and (not key.startswith('forgery-family-'))}, {'forgery-polarizer': (1, ['weapon-skill-dieyipianzhenti', 'weapon-skill-duoyipianzhenti', 'weapon-skill-danyipianzhenti']), 'forgery-string': (7, ['skill-duanxudexianxian', 'skill-rugedexianxian']), 'forgery-string-current': (2, ['skill-ninggudexianxian']), 'forgery-cutting-crystal': (3, ['weapon-skill-gaopinqiexuejingkuai']), 'forgery-tidal-crystal': (4, ['weapon-skill-gaopinhaishisuijing']), 'forgery-phlogiston': (5, ['weapon-skill-canxiangjuran'])})
        options = stock.material_options()
        self.assertEqual(len(options), 49)
        for item in ('weapon-skill-dieyipianzhenti', 'skill-duanxudexianxian', 'skill-rugedexianxian'):
            row = dict(next((row for row in options if row['id'] == item)), target=10)
            self.assertEqual(stock.validate_targets([row]), [row])
        self.assertNotIn('weekly-boss-tianquliulizhixin', {row['id'] for row in options})

    def test_measured_routes_reuse_native_single40_and_restore_selector(self):
        for key in ('forgery-polarizer', 'forgery-string'):
            with self.subTest(route=key):
                route = stock.ROUTES[key]
                child = ForgeryChild()
                child.expected_index = route['native_index']
                self.pending()
                with patch.dict('sys.modules', modules):
                    stock.farm_once(self.parent, child, route)
                self.assertEqual((child.selected_index, child.claims, child.current), (route['native_index'], 1, 200))
                self.assertNotIn('click_on_book_target', child.__dict__)

    def test_forgery_filter_unknown_or_filtered_stops_before_selection_and_spending(self):
        for text in ('武器类型/音感仪', '', '武器类型/全部全部'):
            child = ForgeryChild()
            child.filter_text = text
            self.pending()
            with patch.dict('sys.modules', modules), self.assertRaisesRegex(RuntimeError, '筛选'):
                stock.farm_once(self.parent, child, stock.ROUTES['forgery-string'])
            self.assertFalse(hasattr(child, 'selected_index'))
            self.assertEqual(child.claims, 0)
            self.assertNotIn('click_on_book_target', child.__dict__)
            self.assertTrue(self.parent.config[stock.PENDING_KEY]['pending'])

    def test_forgery_filter_change_or_stop_between_frames_sends_no_selector_input(self):
        for stop in (False, True):
            child = ForgeryChild()
            calls = []
            original = child.wait_ocr

            def read(*args, **kwargs):
                calls.append(1)
                child.filter_text = '武器类型/全部' if len(calls) == 1 else '武器类型/迅刀'
                return original(*args, **kwargs)

            def guard(*args):
                if stop and calls:
                    raise RuntimeError('stopped')
            child.wait_ocr = read
            self.pending()
            with patch.dict('sys.modules', modules), patch.object(control, 'wait_seconds', side_effect=guard):
                with self.assertRaises(RuntimeError):
                    stock.farm_once(self.parent, child, stock.ROUTES['forgery-string'])
            self.assertFalse(hasattr(child, 'selected_index'))
            self.assertEqual(child.claims, 0)

    def test_currency_single_claim_and_fresh_inventory_completion(self):
        option = next((r for r in stock.material_options() if r['id'] == 'shell-credit'))
        self.assertEqual(option, {'id': 'shell-credit', 'name': '贝币', 'route': 'simulation-shell-credit'})
        self.rows = [dict(option, target=1)]
        self.child.expected_selection = 'Shell Credit'
        self.test_full_cycle_fresh_inspections_priority_no_saved_child_changes()

    def test_missing_native_task_fails_before_gameplay_preparation(self):
        self.parent.config[stock.PLAN_KEY] = self.rows
        self.parent.get_task_by_class = lambda cls: None
        inspection = ModuleType('src.task.InventoryInspection')
        inspection.prepare, inspection.load_module, inspection.run_inventory_inspection = (Mock(), Mock(), Mock())
        with patch.dict('sys.modules', dict(modules, **{'src.task.InventoryInspection': inspection})):
            with self.assertRaisesRegex(RuntimeError, '未注册'):
                stock.run_inventory_maintain(self.parent)
        self.parent._prepare_gameplay.assert_not_called()
        inspection.run_inventory_inspection.assert_not_called()
if __name__ == '__main__':
    unittest.main()
