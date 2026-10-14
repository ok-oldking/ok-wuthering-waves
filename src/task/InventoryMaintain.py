from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Opt-in inventory-deficit farming. No changes to native daily/farming plans.

Only calibrated materials with a reviewed native farming route are offered.
Fresh bag/details or reviewed reward-popup quantities are required; never cached stock.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import time
ROOT = inventory_root()
PLAN_KEY = 'Inventory Targets'
PENDING_KEY = '_Inventory Farming Pending'
HISTORY_KEY = '_Inventory Farming Stock'
ROUTES = {'simulation-character-exp': {'name': '模拟训练 · 共鸣促剂', 'cost': 40, 'selection': 'Resonator EXP', 'materials': ['character-exp-basic', 'character-exp-medium', 'character-exp-advanced', 'character-exp-premium']}, 'simulation-weapon-exp': {'name': '模拟训练 · 能源核心', 'cost': 40, 'selection': 'Weapon EXP', 'materials': ['weapon-exp-basic', 'weapon-exp-medium', 'weapon-exp-advanced', 'weapon-exp-premium']}, 'simulation-shell-credit': {'name': '模拟训练 · 贝币', 'cost': 40, 'selection': 'Shell Credit', 'materials': ['shell-credit']}, 'forgery-polarizer': {'name': '凝素领域 · 叠翼偏振体', 'cost': 40, 'kind': 'Forgery', 'native_index': 1, 'materials': ['weapon-skill-dieyipianzhenti', 'weapon-skill-duoyipianzhenti', 'weapon-skill-danyipianzhenti']}, 'forgery-string': {'name': '凝素领域 · 弦线', 'cost': 40, 'kind': 'Forgery', 'native_index': 7, 'materials': ['skill-duanxudexianxian', 'skill-rugedexianxian']}, 'forgery-string-current': {'name': '凝素领域 · 凝固的弦线', 'cost': 40, 'kind': 'Forgery', 'native_index': 2, 'materials': ['skill-ninggudexianxian']}, 'forgery-cutting-crystal': {'name': '凝素领域 · 切削晶块', 'cost': 40, 'kind': 'Forgery', 'native_index': 3, 'materials': ['weapon-skill-gaopinqiexuejingkuai']}, 'forgery-tidal-crystal': {'name': '凝素领域 · 海蚀碎晶', 'cost': 40, 'kind': 'Forgery', 'native_index': 4, 'materials': ['weapon-skill-gaopinhaishisuijing']}, 'forgery-phlogiston': {'name': '凝素领域 · 聚燃体', 'cost': 40, 'kind': 'Forgery', 'native_index': 5, 'materials': ['weapon-skill-canxiangjuran']}}

def load_file(name, path):
    return import_support(path)

def policy(root=ROOT):
    return load_file('wuwa_inventory_deficit_policy', Path(root) / 'tools/inventory-deficit-policy.py')
_family_registry = load_file('wuwa_stock_families', ROOT / 'tools/inventory-wuwa-families.py')
_family_routes = _family_registry.routes()
for _route in ROUTES.values():
    if _route.get('kind') == 'Forgery':
        _match = next((r for r in _family_routes.values() if set(_route['materials']).issubset(r['materials'])), None)
        if _match is None:
            raise ValueError('凝素旧计划未绑定到准确材料系列')
        _route['reward_names'] = _match['reward_names']
ROUTES.update(_family_routes)

def material_options(root=ROOT):
    """Bounded local menu; no native initialization/input. No arbitrary routes."""
    cfg = load_file('wuwa_stock_task_config', Path(root) / 'tools/inventory-task-config.py')
    plan = json.loads(cfg.config_path(root, 'wuwa-inventory-task-plan.json').read_text(encoding='utf-8-sig'))
    if plan.get('schema') != 'inventory-inspection-plan/v1' or plan.get('game') != 'wuwa' or plan.get('ready') is not True or (not isinstance(plan.get('pages'), list)) or (not 1 <= len(plan['pages']) <= 64):
        raise ValueError('仓库识别计划尚未准备好')
    options, seen = ([], set())
    for page in plan['pages']:
        data = cfg.read_calibration(root, page['calibration'], 'wuwa')
        if data.get('game') != 'wuwa' or data.get('ready') is not True:
            raise ValueError('材料标定尚未准备好')
        matches = [row for row in data['materials'] if row['id'] == page['material_id']]
        if len(matches) != 1 or page['material_id'] in seen:
            raise ValueError('材料标定身份重复或缺失')
        seen.add(page['material_id'])
        row = matches[0]
        route = next((key for key, value in ROUTES.items() if row['id'] in value['materials']), None)
        if route:
            options.append({'id': row['id'], 'name': row['name'], 'route': route})
    return options

def validate_targets(rows, root=ROOT):
    result = policy(root).validate_plan(rows, ROUTES)
    options = {row['id']: row for row in material_options(root)}
    for row in result:
        if options.get(row['id']) != {key: row[key] for key in ('id', 'name', 'route')}:
            raise ValueError('此材料或刷取入口尚未接入库存识别')
        native_selection(ROUTES[row['route']])
    return result

def native_selection(route):
    """Only reviewed route constants select native tasks; users cannot supply indexes.

    Only the current measured ALL-filter destinations are listed in ROUTES.
    Runtime filter evidence is required again before the native selector acts.
    """
    if not isinstance(route, dict) or type(route.get('cost')) is not int or route['cost'] != 40:
        raise ValueError('原生材料副本必须是单次40波片')
    kind = route.get('kind', 'Simulation')
    if kind == 'Simulation' and route.get('selection') in ('Resonator EXP', 'Weapon EXP', 'Shell Credit'):
        return (kind, {'Material Selection': route['selection']})
    if kind == 'Forgery' and type(route.get('native_index')) is int and (1 <= route['native_index'] <= 20) and ('selection' not in route):
        return (kind, {'Which Forgery Challenge to Farm': route['native_index']})
    raise ValueError('材料副本类型或已标定入口无效')

def native_child(parent, route):
    kind, _ = native_selection(route)
    if kind == 'Forgery':
        from src.task.ForgeryTask import ForgeryTask
        cls = ForgeryTask
    else:
        from src.task.SimulationTask import SimulationTask
        cls = SimulationTask
    child = parent.get_task_by_class(cls)
    if child is None:
        raise RuntimeError('原生材料副本任务未注册')
    if kind == 'Forgery' and (child.total_number != 20 or child.structure != [5, 5, 5, 5]):
        raise RuntimeError('凝素领域原生列表已改变，需要重新核对入口')
    return child

def resolve_destination(child, parent, route, original_selector):
    from src.task.InventoryBagPort import NativeBagPort
    from src.inventory_support.native_control import wait_seconds
    resolver = load_file('wuwa_stock_destination', ROOT / 'tools/inventory-wuwa-destination.py')
    return resolver.resolve(child, NativeBagPort(child, lambda: wait_seconds(parent, 0)), original_selector, route['reward_names'], lambda: wait_seconds(parent, 0))

def verify_saved(parent, key, value):
    file = Path(parent.config.config_file)
    if file.stat().st_size > 2000000:
        raise RuntimeError('库存任务配置过大')
    with file.open('r+b') as stream:
        if json.loads(stream.read().decode('utf-8-sig')).get(key) != value:
            raise RuntimeError('库存任务记录保存失败，不继续扣体力')
        os.fsync(stream.fileno())

def store_value(parent, key, value):
    before = deepcopy(parent.config.get(key))
    try:
        parent.config[key] = deepcopy(value)
        verify_saved(parent, key, value)
    except Exception:
        parent.config[key] = before
        raise

def strict_current(task):
    expression = re.compile('(?<![\\d.+−-])(\\d+)\\s*/\\s*240(?![\\d.])')
    boxes = task.wait_ocr(0.49, 0.0, 0.92, 0.1, raise_if_not_found=False, match=[expression])
    boxes = boxes if isinstance(boxes, list) else [boxes] if boxes else []
    values = {int(match.group(1)) for box in boxes for match in expression.finditer(box.name)}
    if len(values) != 1 or not 0 <= next(iter(values)) <= 240:
        raise RuntimeError('自然结晶波片未识别，未知不当作0')
    return next(iter(values))

def read_natural(task):
    task.ensure_main(time_out=60)
    task.openF2Book('gray_book_boss')
    try:
        first = strict_current(task)
        task.sleep(1)
        second = strict_current(task)
        if not first <= second <= first + 1:
            raise RuntimeError('自然结晶波片读数不一致，停止补刷')
        return second
    finally:
        task.back(after_sleep=1)

def verify_forgery_filter(child, parent):
    """A filtered list changes ordinal meaning: refuse before its first click.

    Header band measured at2560x1440: x1840..2460,y195..265.
    No filter dropdown is changed automatically; stop on unknown/other filters.
    """
    from src.inventory_support.native_control import wait_seconds
    expected = '武器类型/全部'
    expression = re.compile('^武器类型\\s*/\\s*全部$')
    for index in range(2):
        wait_seconds(parent, 0)
        boxes = child.wait_ocr(1840 / 2560, 195 / 1440, 2460 / 2560, 265 / 1440, raise_if_not_found=False, time_out=3, match=[expression])
        boxes = boxes if isinstance(boxes, list) else [boxes] if boxes else []
        names = [''.join(box.name.split()) for box in boxes if isinstance(getattr(box, 'name', None), str)]
        if names != [expected]:
            raise RuntimeError('凝素领域武器筛选不是“全部”或未识别，停止，不选择副本')
        wait_seconds(parent, 0)
        if index == 0:
            child.sleep(0.15)

@contextmanager
def farming_scope(child, parent, route):
    from src.inventory_support.native_control import wait_seconds
    kind, selection = native_selection(route)
    names = ('config', 'in_combat', 'get_stamina')
    if kind == 'Forgery':
        names += ('click_on_book_target',)
        original_selector = getattr(child, 'click_on_book_target', None)
        if not callable(original_selector):
            raise RuntimeError('凝素领域原生入口选择器缺失，不进入副本')
    saved = {key: (key in child.__dict__, child.__dict__.get(key)) for key in names}
    original_combat = child.in_combat
    deadline = time.monotonic() + 600

    def combat(*args, **kwargs):
        wait_seconds(parent, 0)
        if time.monotonic() >= deadline:
            raise TimeoutError('库存补刷单场超时，不自动重刷')
        return original_combat(*args, **kwargs)
    child.config = dict(parent.config)
    child.config.update(selection)
    child.in_combat = combat

    def read():
        wait_seconds(parent, 0)
        if time.monotonic() >= deadline:
            raise TimeoutError('库存补刷单场超时')
        current = strict_current(child)
        return (current, 0, current)
    child.get_stamina = read
    selections = 0
    if kind == 'Forgery':

        def select(serial_number, total_number, structure=None):
            nonlocal selections
            wait_seconds(parent, 0)
            if selections or type(serial_number) is not int or serial_number != route['native_index'] or (type(total_number) is not int) or (total_number != 20) or (structure != [5, 5, 5, 5]):
                raise RuntimeError('凝素领域入口序号或列表结构改变，停止，不重复选择')
            verify_forgery_filter(child, parent)
            selections += 1
            return resolve_destination(child, parent, route, original_selector)
        child.click_on_book_target = select
    try:
        yield
        if kind == 'Forgery' and selections != 1:
            raise RuntimeError('凝素领域入口未经过核验，不将本场计为完成')
    finally:
        for key, (owned, value) in saved.items():
            if owned:
                child.__dict__[key] = value
            else:
                child.__dict__.pop(key, None)

def farm_once(parent, child, route):
    from src.inventory_support.native_control import wait_seconds
    from src.inventory_support.native_control import counted_natural
    from src.task.WWOneTimeTask import WWOneTimeTask
    kind, _ = native_selection(route)
    if kind == 'Forgery' and (child.total_number != 20 or child.structure != [5, 5, 5, 5]):
        raise RuntimeError('凝素领域原生列表已改变，拒绝进入未知副本')
    if child.stamina_once != route['cost']:
        raise RuntimeError('上游副本波片消耗已改变，拒绝执行')
    pending = deepcopy(parent.config.get(PENDING_KEY))
    if not isinstance(pending, dict) or pending.get('pending') is not True:
        raise RuntimeError('缺少本场库存补刷待核实记录')

    def before_claim(attempt):
        wait_seconds(parent, 0)
        if attempt != 1 or not child.has_claim_stamina():
            raise RuntimeError('未确认材料奖励窗口，不扣波片')
        if parent.config.get(PENDING_KEY) != pending:
            raise RuntimeError('本场库存补刷记录发生变化')
        verify_saved(parent, PENDING_KEY, pending)
    with farming_scope(child, parent, route):
        WWOneTimeTask.run(child)
        child.make_sure_in_world()
        with counted_natural(child, 1, before_claim) as state:
            method = child.farm_forgery if kind == 'Forgery' else child.farm_simulation
            method(daily=False, used_stamina=0, config=dict(child.config))
        if state['attempts'] != 1 or state['used'] != route['cost']:
            raise RuntimeError('库存补刷未完成单场领奖，不自动重刷')

def run_inventory_maintain(parent, root=ROOT):
    from src.task.InventoryInspection import run_inventory_inspection, prepare, load_module
    from src.inventory_support.native_control import wait_seconds
    rows = validate_targets(parent.config.get(PLAN_KEY, []), root)
    if parent.config.get(PENDING_KEY):
        raise RuntimeError('上次库存补刷扣体力尚未核实，请先检查日志；不自动重刷')
    stock_policy = policy(root)
    conversion_families = stock_policy.equivalence.load_families(root, 'wuwa')
    selected = [row['id'] for row in stock_policy.equivalence.observation_rows(rows, conversion_families)]
    bridge = load_module('wuwa_stock_bridge_preflight', Path(root) / 'tools/inventory-task-session.py')
    navigation = load_module('wuwa_stock_navigation_preflight', Path(root) / 'tools/inventory-native-navigation.py')
    prepare(root, bridge, navigation, selected)
    children = {row['route']: native_child(parent, ROUTES[row['route']]) for row in rows}
    parent._prepare_gameplay()
    child = children[rows[0]['route']]

    def inspect():
        report = run_inventory_inspection(parent, root, selected_ids=selected)
        history = {'observed_at': datetime.now(timezone.utc).isoformat(), 'materials': [{key: item.get(key) for key in ('id', 'name', 'quantity', 'status')} for item in report['materials'] if item.get('id') in selected]}
        store_value(parent, HISTORY_KEY, history)
        return report
    result = policy(root).run_cycle(rows, ROUTES, game='wuwa', inspect=inspect, read_stamina=lambda: read_natural(child), farm_once=lambda row, route: farm_once(parent, children[row['route']], route), journal=lambda record: store_value(parent, PENDING_KEY, record), pending=parent.config.get(PENDING_KEY), guard=lambda: wait_seconds(parent, 0), conversion_families=conversion_families)
    parent.log_info('InventoryMaintain/v1 ' + json.dumps(result, ensure_ascii=False))
    labels = {'targets_met': '目标已达标', 'stamina_insufficient': '自然波片不足，已结束', 'run_budget_reached': '本次场数上限，未全部达标'}
    if result['state'] == 'targets_met' and any((f['requires_conversion'] for f in result['equivalence']['families'])):
        labels['targets_met'] = '折算已够用，使用前请合成或转换'
    elif result['state'] == 'targets_met' and any((f['requires_substitution'] for f in result['equivalence']['families'])):
        labels['targets_met'] = '经验总量已够用，不再补刷'
    parent.info_set('库存保持', labels[result['state']])
    if result['state'] == 'run_budget_reached':
        raise RuntimeError(labels[result['state']])
    return result
