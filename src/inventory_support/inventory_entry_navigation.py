from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Reviewed WuWa simulation/forgery book prefixes: never start combat.

Coordinates are the current native SimulationTask prefix, not material popup
geometry. A candidate must supply current, independently reviewed screen anchors.
No production route is enabled by importing this module.
"""
from contextlib import contextmanager
import hashlib
import inspect
from math import isfinite
from pathlib import Path
import re
MATERIALS = {**{f'character-exp-{quality}': ('character_exp', 0) for quality in ('basic', 'medium', 'advanced', 'premium')}, **{f'weapon-exp-{quality}': ('weapon_exp', 1) for quality in ('basic', 'medium', 'advanced', 'premium')}, 'shell-credit': ('currency', 2)}
FORGERY_MATERIALS = {'weapon-skill-dieyipianzhenti': ('叠翼偏振体', 'weapon_promotion'), 'skill-duanxudexianxian': ('断续的弦线', 'skill'), 'skill-rugedexianxian': ('如歌的弦线', 'skill'), 'weapon-skill-duoyipianzhenti': ('多翼偏振体', 'weapon_promotion'), 'weapon-skill-danyipianzhenti': ('单翼偏振体', 'weapon_promotion'), 'skill-ninggudexianxian': ('凝固的弦线', 'skill'), 'weapon-skill-gaopinqiexuejingkuai': ('高频切削晶块', 'weapon_promotion'), 'weapon-skill-gaopinhaishisuijing': ('高频海蚀碎晶', 'weapon_promotion'), 'weapon-skill-canxiangjuran': ('残响聚燃体', 'weapon_promotion')}
FORGERY_REWARDS = {'weapon-skill-dieyipianzhenti': (1, 1371, '武器及技能材料·迅刀'), 'skill-duanxudexianxian': (7, 1564, '武器及技能材料·音感仪'), 'skill-rugedexianxian': (7, 1371, '武器及技能材料·音感仪'), 'weapon-skill-duoyipianzhenti': (1, 1483, '武器及技能材料·迅刀'), 'weapon-skill-danyipianzhenti': (1, 1565, '武器及技能材料·迅刀'), 'skill-ninggudexianxian': (2, 1483, '武器及技能材料·音感仪'), 'weapon-skill-gaopinqiexuejingkuai': (3, 1483, '武器及技能材料·长刃'), 'weapon-skill-gaopinhaishisuijing': (4, 1483, '武器及技能材料·臂铠'), 'weapon-skill-canxiangjuran': (5, 1483, '武器及技能材料·佩枪')}
BASE_SOURCE_SHA256 = '21bc47a464978dce6f2062eb811f8c6d695c0cc85a39fca041305c7f329acf57'

def exact_coordinate(value, expected):
    """按有限数值的精确表示校验原生点击常量，不放宽坐标范围。"""
    return (type(value) in (int, float) and isfinite(value)
            and float(value).hex() == float(expected).hex())

def anchors(value):
    if not isinstance(value, list) or not 2 <= len(value) <= 3 or any((not isinstance(a, dict) or set(a) != {'text', 'roi'} or (not isinstance(a.get('text'), str)) or (not 1 <= len(a['text'].strip()) <= 64) for a in value)) or (len({a['text'] for a in value}) != len(value)):
        raise ValueError('Entry transport requires two distinct reviewed screen labels')
    for anchor in value:
        roi = anchor['roi']
        if not isinstance(roi, list) or len(roi) != 4 or any((type(n) is not int for n in roi)) or (roi[0] < 0) or (roi[1] < 0) or (roi[2] <= 0) or (roi[3] <= 0) or (roi[0] + roi[2] > 1920) or (roi[1] + roi[3] > 1080):
            raise ValueError('Entry transport anchor outside canonical frame')
    return value

def validate(page, descriptor):
    if page.get('game') != 'wuwa' or page.get('candidate_only') is not True or len(page.get('materials', [])) != 1 or (not isinstance(descriptor, dict)):
        raise ValueError('Explicit reviewed WuWa book prefix required')
    item = page['materials'][0]
    if descriptor.get('strategy') == 'wuwa_forgery_reward_list':
        if set(descriptor) != {'strategy', 'book_anchors', 'materials_anchors', 'forgery_anchors'} or FORGERY_MATERIALS.get(item.get('id')) != (item.get('name'), item.get('category')):
            raise ValueError('Reward list requires an exact measured material; no arbitrary index')
        anchors(descriptor['book_anchors'])
        anchors(descriptor['materials_anchors'])
        labels = anchors(descriptor['forgery_anchors'])
        if {''.join(row['text'].split()) for row in labels} != {'凝素领域', '武器类型/全部'}:
            raise ValueError('Reward list requires the measured unfiltered forgery headers')
        return FORGERY_REWARDS[item['id']][0]
    if descriptor.get('strategy') == 'wuwa_forgery_book':
        if set(descriptor) != {'strategy', 'book_anchors', 'forgery_anchors', 'native_index'} or type(descriptor.get('native_index')) is not int or (not 1 <= descriptor['native_index'] <= 20) or (FORGERY_MATERIALS.get(item.get('id')) != (item.get('name'), item.get('category'))):
            raise ValueError('Forgery prefix requires an exact eligible material and reviewed index')
        anchors(descriptor['book_anchors'])
        anchors(descriptor['forgery_anchors'])
        return descriptor['native_index']
    if set(descriptor) != {'strategy', 'book_anchors', 'simulation_anchors'} or descriptor.get('strategy') != 'wuwa_simulation_book':
        raise ValueError('Only explicit reviewed WuWa book prefixes are supported')
    binding = MATERIALS.get(item.get('id'))
    if binding is None or item.get('category') != binding[0]:
        raise ValueError('Material does not belong to the reviewed simulation destination')
    anchors(descriptor['book_anchors'])
    anchors(descriptor['simulation_anchors'])
    return binding[1]

def pause(port, seconds):
    method = getattr(port, 'pause', None)
    if not callable(method):
        method = port.task.sleep
    method(seconds)

def anchor_text(value):
    text = ''.join(value.split())
    if text.startswith('武器及技能材料'):
        candidate = text.replace('・', '·')
        if candidate in {'武器及技能材料·' + name for name in ('迅刀', '音感仪', '长刃', '臂铠', '佩枪')}:
            return candidate
    return text

def matches(port, labels, guard):
    for i in range(2):
        guard()
        frame = port._frame()
        for anchor in labels:
            guard()
            token = port._read(anchor['roi'], frame)
            if not isinstance(token, dict):
                return False
            confidence = token.get('confidence')
            if not isinstance(token.get('text'), str) or anchor_text(token['text']) != anchor_text(anchor['text']) or isinstance(confidence, bool) or (not isinstance(confidence, (int, float))) or (not isfinite(confidence)) or (not 0.9 <= confidence <= 1):
                return False
        guard()
        if i == 0:
            pause(port, 0.15)
    return True

def wait_labels(port, labels, guard):
    for _ in range(12):
        if matches(port, labels, guard):
            return True
        pause(port, 0.2)
        guard()
    return False

def world_verified(port, guard):
    """Two independent world observations; no login or ensure_main fallback."""
    for index in range(2):
        guard()
        port._frame()
        if port.task.in_team_and_world() is not True:
            return False
        guard()
        if index == 0:
            pause(port, 0.15)
    return True

def leave_verified_menu(port, guard, *, labels=None, bag_page=None):
    """Close exactly one known menu, then observe only. Unknown stays untouched.

    A bag transition additionally requires its last captured detail label. This
    is not a general dialog closer; a failed animation never sends Escape twice.
    """
    if (labels is None) == (bag_page is None):
        raise ValueError('One exact menu binding required')
    if labels is not None:
        anchors(labels)
        verified = matches(port, labels, guard)
    else:
        page, item_id = bag_page
        item = next((row for row in page['materials'] if row['id'] == item_id))
        verified = True
        for index in range(2):
            guard()
            if port.page_verified(page) is not True:
                verified = False
                break
            token = port.read_detail(item['label_roi'])
            if not isinstance(token, dict) or ''.join(token.get('text', '').split()) != ''.join(item['name'].split()) or type(token.get('confidence')) not in (int, float) or (not 0.9 <= token['confidence'] <= 1):
                verified = False
                break
            if index == 0:
                pause(port, 0.15)
    if not verified:
        return False
    guard()
    port.task.send_key('esc')
    guard()
    for _ in range(12):
        pause(port, 0.2)
        if world_verified(port, guard):
            return True
    return False

@contextmanager
def category_click_scope(task, guard, *, y=0.3):
    """Guard the native prefix's only category click; restore on every exit."""
    owned, saved = ('click_relative' in task.__dict__, task.__dict__.get('click_relative'))
    original = task.click_relative
    calls = 0

    def click(x, y, *args, **kwargs):
        nonlocal calls
        guard()
        if calls or not exact_coordinate(x, 0.24) or not exact_coordinate(y, expected_y):
            raise RuntimeError('Native book category prefix changed; no extra input')
        calls += 1
        result = original(x, y, *args, **kwargs)
        guard()
        return result
    expected_y = y
    task.click_relative = click
    try:
        yield
        if calls != 1:
            raise RuntimeError('Native book category selection not executed exactly once')
    finally:
        if owned:
            task.__dict__['click_relative'] = saved
        else:
            task.__dict__.pop('click_relative', None)

def verify_forgery_selector(task):
    """Reject native updater changes before observations or controller access."""
    method = getattr(task, 'click_on_book_target', None)
    function = getattr(method, '__func__', None)
    if function is None or function.__qualname__ != 'BaseWWTask.click_on_book_target':
        raise ValueError('Reviewed native book selector unavailable')
    source = Path(inspect.getsourcefile(function) or '')
    if source.name != 'BaseWWTask.py' or not source.is_file() or source.stat().st_size > 1024 * 1024 or (hashlib.sha256(source.read_bytes()).hexdigest() != BASE_SOURCE_SHA256):
        raise ValueError('Native book selector changed; review before using forgery prefix')

@contextmanager
def forgery_click_scope(task, port, labels, guard, *, on_selected=None):
    """Permit bounded native list scroll/selection, never its travel button.

    Each input must still be on the independently calibrated forgery page.
    Boxes come from the reviewed selector's boss_proceed feature detector.
    Methods are restored after success, missing labels, cancellation or error.
    """
    names = ('click', 'find_feature')
    saved = {name: (name in task.__dict__, task.__dict__.get(name)) for name in names}
    click, find = (task.click, task.find_feature)
    boxes, scrolls, selected = ([], 0, 0)
    forwarded_scroll = None

    def features(name, *args, **kwargs):
        guard()
        if name != 'boss_proceed' or not exact_coordinate(kwargs.get('threshold'), 0.8):
            raise RuntimeError('Native forgery feature selector changed')
        result = find(name, *args, **kwargs)
        boxes[:] = list(result or [])
        if len(boxes) > (5 if callable(on_selected) else 4):
            raise RuntimeError('Native forgery list has unexpected visible rows')
        guard()
        return result

    def checked_click(target, y=None, *args, **kwargs):
        nonlocal scrolls, selected, forwarded_scroll
        guard()
        if selected or not matches(port, labels, guard):
            raise RuntimeError('Forgery entry page unverified; no extra input')
        if forwarded_scroll is not None:
            expected = forwarded_scroll
            forwarded_scroll = None
            if type(target) is not int or type(y) is not int or (target, y) != expected:
                raise RuntimeError('Native scrollbar coordinate conversion changed')
            result = click(target, y, *args, **kwargs)
            guard()
            return result
        if type(target) in (int, float):
            if not exact_coordinate(target, 0.973) or type(y) not in (int, float) or (not isfinite(y)) or (not 0.191 <= y <= 0.8806) or (scrolls >= 3):
                raise RuntimeError('Native forgery attempted an unreviewed click')
            scrolls += 1
            boxes.clear()
            forwarded_scroll = (int(task.width * target), int(task.height * y))
            try:
                result = click(target, y, *args, **kwargs)
            finally:
                forwarded_scroll = None
        else:
            if y is not None or not any((target is box for box in boxes)):
                raise RuntimeError('Forgery selection is not a fresh native list button')
            x, row_y = target.center()
            width, height = (task.width, task.height)
            if any((type(n) not in (int, float) or not isfinite(n) for n in (x, row_y, width, height))) or width <= 0 or height <= 0 or (not 0.9113 <= x / width <= 0.9613) or (not 0.229 <= row_y / height <= 0.861):
                raise RuntimeError('Forgery selection outside native list region')
            selected += 1
            result = on_selected(target) if on_selected is not None else click(target, *args, **kwargs)
        guard()
        return result
    task.click, task.find_feature = (checked_click, features)
    try:
        yield
        if selected != 1:
            raise RuntimeError('Native forgery entry not selected exactly once')
    finally:
        for name, (owned, value) in saved.items():
            if owned:
                task.__dict__[name] = value
            else:
                task.__dict__.pop(name, None)

def navigate(port, page, descriptor, entry_anchors, guard):
    """World -> configured guidebook -> native category -> reward preview.

    Unknown dialog/title/login/bag is not dismissed. Each selection happens once;
    failed animation observes only, never retries a toggle. Full native teleport,
    ensure_main, team challenge, farming and claim functions are never invoked.
    """
    index = validate(page, descriptor)
    anchors(entry_anchors)
    if not all((callable(getattr(port, name, None)) for name in ('_frame', '_read', 'click_cell'))):
        raise ValueError('Reviewed native frame/OCR/click port required')
    task = getattr(port, 'task', None)
    if task is None or not all((callable(getattr(task, name, None)) for name in ('in_team_and_world', 'send_key', 'open_boss_book', 'click_relative'))):
        raise ValueError('Native WuWa book prefix unavailable')
    reward_list = descriptor['strategy'] == 'wuwa_forgery_reward_list'
    forgery = descriptor['strategy'] == 'wuwa_forgery_book' or reward_list
    if forgery:
        verify_forgery_selector(task)
        if not all((callable(getattr(task, name, None)) for name in ('click', 'find_feature'))):
            raise ValueError('Native forgery list controller unavailable')
    if matches(port, entry_anchors, guard):
        return True
    training = descriptor['forgery_anchors' if forgery else 'simulation_anchors']
    if not matches(port, training, guard):
        book = descriptor['book_anchors']
        materials = descriptor.get('materials_anchors', book)
        if not matches(port, book, guard) and (not (reward_list and matches(port, materials, guard))):
            for i in range(2):
                guard()
                port._frame()
                if task.in_team_and_world() is not True:
                    return False
                guard()
                if i == 0:
                    pause(port, 0.15)
            key = task.key_config.get('Guidebook Key', task.key_config.get('索拉指南', 'f2'))
            if not isinstance(key, str) or re.fullmatch('(?:[a-zA-Z0-9]|[fF](?:[1-9]|1[0-2]))', key) is None:
                raise ValueError('Configured guidebook key is not a single reviewed key')
            guard()
            task.send_key(key)
            guard()
            if reward_list:
                for _ in range(12):
                    if matches(port, book, guard) or matches(port, materials, guard):
                        break
                    pause(port, 0.2)
                else:
                    return False
            elif not wait_labels(port, book, guard):
                return False
        if reward_list and (not matches(port, materials, guard)):
            if not matches(port, book, guard):
                return False
            guard()
            port.click_cell([77, 320])
            guard()
            if not wait_labels(port, materials, guard):
                return False
        guard()
        with category_click_scope(task, guard, y=0.4 if forgery else 0.3):
            task.open_boss_book('ningsu' if forgery else 'moni')
        guard()
        if not wait_labels(port, training, guard):
            return False
    if forgery:
        if reward_list:
            return wait_labels(port, entry_anchors, guard)
        with forgery_click_scope(task, port, training, guard):
            task.click_on_book_target(index, 20, [5, 5, 5, 5])
        return wait_labels(port, entry_anchors, guard)
    guard()
    port.click_cell([round(0.973 * 1920), round(0.8806 * 1080)])
    guard()
    if not wait_labels(port, training, guard):
        return False
    guard()
    port.click_cell([round(0.898 * 1920), round((0.533 + index * 0.14) * 1080)])
    guard()
    return wait_labels(port, entry_anchors, guard)

class _RewardRowLocated(Exception):

    def __init__(self, y):
        self.y = y

def open_forgery_reward(port, page, descriptor, entry_anchors, popup_anchors, guard):
    """Reuse native row positioning, never click its challenge/travel button.

    No native wait_feature/team/teleport follows the intercepted row selection.
    Independently verify row family twice, then click its measured reward icon.
    Exact material+owned-label observations authorize reading, not spending.
    """
    index = validate(page, descriptor)
    if descriptor['strategy'] != 'wuwa_forgery_reward_list':
        raise ValueError('Direct reward-list transport required')
    if not navigate(port, page, descriptor, entry_anchors, guard):
        return False
    task = port.task
    guard()

    def located(box):
        guard()
        raise _RewardRowLocated(box.center()[1] * 1080 / task.height)
    try:
        with forgery_click_scope(task, port, descriptor['forgery_anchors'], guard, on_selected=located):
            task.click_on_book_target(index, 20, [5, 5, 5, 5])
    except _RewardRowLocated as row:
        guard()
        y = round(row.y)
    else:
        raise RuntimeError('Native reward row was not intercepted; no reward click')
    _, x, family = FORGERY_REWARDS[page['materials'][0]['id']]
    row_anchor = {'text': family, 'roi': [887, y + 18, 310, 40]}
    if not matches(port, entry_anchors + [row_anchor], guard):
        return False
    for field in ('scrollbar', 'selected_thumb', 'selection_policy'):
        if hasattr(port, field):
            setattr(port, field, None)
    guard()
    port.click_cell([x, y])
    guard()
    return wait_labels(port, popup_anchors, guard)
