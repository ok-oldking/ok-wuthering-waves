from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Candidate-only native simulation selection, stopping before cards/combat.

An optional reviewed native training-book prefix reaches that list from world.
No general BackToNormalWorld, login or refill fallback is reachable.
"""
from contextlib import contextmanager
import importlib.util
from math import isfinite
from pathlib import Path
from src.inventory_support import inventory_entry_navigation as labels
MATERIALS = {'basic-physical-chip': ('基础物理芯片', 'skill', '代理人技能', '刚性测试'), 'basic-attack-seal': ('初阶强攻认证章', 'character_promotion', '代理人晋升', '强攻演练'), 'support-component': ('支援组件', 'weapon_promotion', '音擎改装', '支援分频试验'), 'w-engine-energy-module': ('音擎能源模块', 'weapon_exp', '基础材料', '音擎专项'), 'senior-investigator-log': ('资深调查员记录', 'character_exp', '基础材料', '调查专项'), 'denny': ('丁尼', 'currency', '基础材料', '赏金专项'), 'advanced-attack-seal': ('高阶强攻认证章', 'character_promotion', '代理人晋升', '强攻演练'), 'pioneer-certification-seal': ('先行者认证章', 'character_promotion', '代理人晋升', '强攻演练'), 'advanced-physical-chip': ('进阶物理芯片', 'skill', '代理人技能', '刚性测试'), 'specialized-physical-chip': ('特化物理芯片', 'skill', '代理人技能', '刚性测试'), 'basic-freeze-chip': ('基础冰结芯片', 'skill', '代理人技能', '冰结测试'), 'advanced-freeze-chip': ('进阶冰结芯片', 'skill', '代理人技能', '冰结测试'), 'specialized-freeze-chip': ('特化冰结芯片', 'skill', '代理人技能', '冰结测试')}
from src.inventory_support import inventory_zzz_families as family_registry
MATERIALS.update(family_registry.preview_materials())

def exact_native_point(op, area_name, expected, target_point, *, center=False):
    """Bind a native fuzzy-selected point to exact, confident fresh text."""
    area = op.ctx.screen_loader.get_area('快捷手册', area_name)
    for _ in range(2):
        screen = op.screenshot()
        points = []
        kwargs = {'merge_line_distance': 40} if center else {}
        for text, mrl in op.ctx.ocr.crop_and_run_ocr(screen, area.rect, **kwargs).items():
            candidate = mrl.max
            if ''.join(text.split()) != ''.join(expected.split()) or candidate is None:
                continue
            score = candidate.confidence
            if isinstance(score, bool) or not isinstance(score, (int, float)) or (not isfinite(score)) or (not 0.9 <= score <= 1):
                continue
            points.append(area.left_top + (candidate.center if center else candidate))
        if len(points) != 1 or abs(points[0].x - target_point.x) > 4 or abs(points[0].y - target_point.y) > 4:
            return False
    return True

@contextmanager
def category_click_scope(op, guard, expected):
    controller = op.ctx.controller
    original = controller.click
    owned = 'click' in controller.__dict__
    saved = controller.__dict__.get('click')

    def click(point, *args, **kwargs):
        guard()
        if op.ctx.controller is not controller or args or kwargs or (not exact_native_point(op, '分类列表', expected, point, center=True)):
            raise RuntimeError('手册分类点击位置未由准确名称核实')
        guard()
        result = original(point)
        guard()
        return result
    controller.click = click
    try:
        yield
    finally:
        if controller.__dict__.get('click') is click:
            if owned:
                controller.click = saved
            else:
                controller.__dict__.pop('click', None)

def validate(page, descriptor):
    if page.get('game') != 'zzz' or page.get('candidate_only') is not True or len(page.get('materials', [])) != 1 or (not isinstance(descriptor, dict)) or (set(descriptor) not in ({'strategy', 'category_anchors', 'type_anchors'}, {'strategy', 'category_anchors', 'type_anchors', 'transport'})) or (descriptor.get('strategy') != 'zzz_simulation_preview'):
        raise ValueError('Only explicit reviewed ZZZ simulation preview is supported')
    item = page['materials'][0]
    binding = MATERIALS.get(item.get('id'))
    if binding is None or (item.get('name'), item.get('category')) != binding[:2]:
        raise ValueError('Material is not an exact reviewed simulation destination')
    labels.anchors(descriptor['category_anchors'])
    labels.anchors(descriptor['type_anchors'])
    if binding[2] not in [a['text'] for a in descriptor['type_anchors']]:
        raise ValueError('Mission list must identify the selected native type')
    if 'transport' in descriptor:
        transport = descriptor['transport']
        if not isinstance(transport, dict) or set(transport) != {'strategy', 'book_anchors', 'simulation_book_anchors', 'confirmation_anchors'} or transport.get('strategy') != 'native_training_book':
            raise ValueError('Only the reviewed native training-book prefix is supported')
        for key in ('book_anchors', 'simulation_book_anchors', 'confirmation_anchors'):
            labels.anchors(transport[key])
        if binding[2] not in [a['text'] for a in transport['simulation_book_anchors']]:
            raise ValueError('Training book must identify the selected simulation type')
    return binding

def create_transport(ctx, mission_type, guard, book_check, simulation_check, confirm_check, arrival_check):
    """Reuse only category/type/go bodies, never the general transport graph."""
    from one_dragon.base.operation.operation import Operation
    from one_dragon.base.operation.operation_edge import node_from
    from one_dragon.base.operation.operation_node import operation_node
    from one_dragon.utils.i18_utils import gt
    from zzz_od.operation.compendium.compendium_choose_category import CompendiumChooseCategory
    from zzz_od.operation.compendium.compendium_choose_mission_type import CompendiumChooseMissionType

    class TrainingTransport(Operation):

        def __init__(self):
            Operation.__init__(self, ctx, node_max_retry_times=3, op_name='库存只读训练入口', timeout_seconds=90, need_check_game_win=False, op_to_enter_game=None)
            self.category_name, self.mission_type = ('实战模拟室', mission_type)

        @operation_node(name='手册分类', is_start_node=True, node_max_retry_times=3)
        def choose_category(self):
            guard()
            if not book_check():
                return self.round_fail('训练手册画面未核实')
            self.last_screenshot = self.screenshot()
            guard()
            with category_click_scope(self, guard, gt(self.category_name, 'game')):
                result = CompendiumChooseCategory.choose_tab(self)
            guard()
            return result

        @node_from(from_name='手册分类')
        @operation_node(name='手册前往', node_max_retry_times=12)
        def choose_type(self):
            guard()
            if not simulation_check():
                return self.round_fail('实战模拟室手册未核实')
            self.last_screenshot = self.screenshot()
            guard()
            result = CompendiumChooseMissionType.choose_mission_type(self)
            guard()
            return result

        def handle_scroll(self, area):
            guard()
            return CompendiumChooseMissionType.handle_scroll(self, area)

        def handle_go_button(self, screen, target_point):
            guard()
            if not simulation_check() or not exact_native_point(self, '副本列表', gt(self.mission_type.mission_type_name, 'game'), target_point):
                return self.round_fail('手册目标不是已核实的副本类型')
            screen = self.screenshot()
            guard()
            result = CompendiumChooseMissionType.handle_go_button(self, screen, target_point)
            guard()
            return result

        @node_from(from_name='手册前往')
        @operation_node(name='手册确认', node_max_retry_times=1)
        def confirm(self):
            guard()
            if arrival_check():
                return self.round_success('库存预览入口已到达')
            if not confirm_check():
                return self.round_fail('传送确认弹窗未核实')
            screen = self.screenshot()
            guard()
            result = self.round_by_find_and_click_area(screen, '快捷手册', '传送确认')
            guard()
            if not result.is_success or not arrival_check():
                return self.round_fail('传送后的库存预览入口未核实')
            return self.round_success('库存预览入口已到达')
    if mission_type is None or mission_type.is_agent_plan or mission_type.category.category_name != '实战模拟室' or (mission_type.category.tab.tab_name != '训练'):
        raise ValueError('Only exact non-agent native training simulation destinations are allowed')
    return TrainingTransport()

def transport_from_world(port, descriptor, binding, guard):
    """One native world button, bounded book prefix; no unknown-screen input."""
    cfg = descriptor['transport']
    book = lambda: labels.matches(port, cfg['book_anchors'], guard)
    ctx = port.op.ctx
    mission_type = ctx.compendium_service.get_mission_type_data('训练', '实战模拟室', binding[2])
    operation = create_transport(ctx, mission_type, guard, book, lambda: labels.wait_labels(port, cfg['simulation_book_anchors'], guard), lambda: labels.wait_labels(port, cfg['confirmation_anchors'], guard), lambda: labels.wait_labels(port, descriptor['category_anchors'], guard) or labels.matches(port, descriptor['type_anchors'], guard))
    if not book():
        if not callable(getattr(port, '_screen', None)):
            raise ValueError('Native world screen verifier required')
        for _ in range(2):
            guard()
            if port._screen(port._frame()) != '大世界-普通':
                return False
            guard()
        frame = port._frame()
        result = port.op.round_by_find_and_click_area(frame, '大世界-普通', '快捷手册')
        guard()
        if not result.is_success or not labels.wait_labels(port, cfg['book_anchors'], guard):
            return False
    guard()
    result = operation.execute()
    guard()
    return result.success and result.status == '库存预览入口已到达'

def create_preview(ctx, plan, guard, category_check, type_check):
    """Build a NEW three-node graph; never inherit the full battle graph."""
    from one_dragon.base.operation.operation import Operation
    from one_dragon.base.operation.operation_edge import node_from
    from one_dragon.base.operation.operation_node import operation_node
    from zzz_od.operation.compendium.combat_simulation import CombatSimulation

    class Preview(Operation):

        def __init__(self):
            Operation.__init__(self, ctx, node_max_retry_times=3, op_name='库存只读副本预览', timeout_seconds=60, need_check_game_win=False, op_to_enter_game=None)
            self.plan, self.scroll_count = (plan, 0)

        def call(self, method, check):
            guard()
            if not check():
                return self.round_fail('库存预览画面未核实')
            self.last_screenshot = self.screenshot()
            guard()
            result = method(self)
            guard()
            return result

        @operation_node(name='预览入口', is_start_node=True, node_max_retry_times=3)
        def entry(self):
            guard()
            if category_check():
                return self.round_success(CombatSimulation.STATUS_NEED_TYPE)
            if type_check():
                return self.round_success()
            return self.round_fail('库存预览入口未知')

        @node_from(from_name='预览入口', status=CombatSimulation.STATUS_NEED_TYPE)
        @operation_node(name='预览类型', node_max_retry_times=3)
        def choose_type(self):
            return self.call(CombatSimulation.choose_mission_type, category_check)

        @node_from(from_name='预览入口')
        @node_from(from_name='预览类型')
        @operation_node(name='预览副本', node_max_retry_times=11)
        def choose_mission(self):
            return self.call(CombatSimulation.choose_mission, type_check)
    if plan.is_agent_plan:
        raise ValueError('Agent templates are not read-only inventory destinations')
    return Preview()

@contextmanager
def input_scope(ctx, guard):
    from zzz_od.application.inventory_maintain.inventory_maintain import GuardedController
    original = ctx.controller
    if original is None:
        raise ValueError('Native controller not initialized')
    proxy = GuardedController(original, guard)
    proxy.check()
    ctx.controller = proxy
    try:
        yield proxy.check
    finally:
        proxy.closed = True
        if ctx.controller is proxy:
            ctx.controller = original

def native_plan(ctx, item_id, binding):
    from zzz_od.application.inventory_maintain.inventory_maintain import ROUTES, build_plan
    route = ROUTES.get(item_id)
    if not isinstance(route, dict) or route.get('type') != binding[2] or route.get('mission') != binding[3] or (route.get('cost') != 20) or (route.get('materials') != [item_id]):
        raise ValueError('Installed native preview destination changed')
    return build_plan(ctx, route)

def navigate(port, page, descriptor, entry_anchors, guard):
    binding = validate(page, descriptor)
    labels.anchors(entry_anchors)
    if binding[3] not in [a['text'] for a in entry_anchors]:
        raise ValueError('Reward entry must identify the exact native mission')
    if not all((callable(getattr(port, name, None)) for name in ('_frame', '_read', 'pause'))):
        raise ValueError('Native ZZZ capture/OCR/pause port required')
    if labels.matches(port, entry_anchors, guard):
        return True
    category_check = lambda: labels.matches(port, descriptor['category_anchors'], guard)
    type_check = lambda: labels.matches(port, descriptor['type_anchors'], guard)
    at_preview = category_check() or type_check()
    if not at_preview and 'transport' not in descriptor:
        return False
    ctx = port.op.ctx
    guard()
    plan = native_plan(ctx, page['materials'][0]['id'], binding)
    with input_scope(ctx, guard) as checked:
        if not at_preview:
            if transport_from_world(port, descriptor, binding, checked) is not True:
                return False
        settled_type = lambda: labels.wait_labels(port, descriptor['type_anchors'], checked)
        preview = create_preview(ctx, plan, checked, category_check, settled_type)
        checked()
        result = preview.execute()
        checked()
        if not result.success or result.status != '选择成功':
            return False
        return labels.wait_labels(port, entry_anchors, checked)
