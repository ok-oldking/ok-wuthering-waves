from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Resolve a forgery family by its *fresh reward identity*, not its ordinal.

Native book selector supplies row geometry. Its challenge click is intercepted;
only a reviewed reward icon is opened. Unknown popups stop without dismissal.
No travel/combat/claim is reachable until an exact family has been verified.
"""
import importlib.util
from pathlib import Path

def load_file(name, file):
    return import_support(file)

def resolve(task, port, native_select, expected_names, guard):
    entry = load_file('wuwa_destination_entry', 'inventory-entry-navigation.py')
    registry = load_file('wuwa_destination_families', 'inventory-wuwa-families.py')
    from types import SimpleNamespace
    entry.verify_forgery_selector(SimpleNamespace(click_on_book_target=native_select))
    families = [f['qualities'] for f in registry.families()]
    legal = [tuple((item['name'] for item in family)) for family in families]
    if tuple(expected_names) not in legal:
        raise ValueError('Exact reviewed four-quality family required')
    all_names = {name for family in legal for name in family}
    import json
    navigation = json.loads((Path(__file__).resolve().parents[1] / 'config/wuwa-forgery-popup-navigation.json').read_text(encoding='utf-8'))
    reference = navigation['tabs']['叠翼偏振体']
    headers = reference['entry_navigation']['forgery_anchors']
    popup_name = [722, 153, 268, 45]
    owned = [dict(text='拥有', roi=[722, 368, 65, 37])]
    for index in range(1, 21):
        guard()
        if not entry.matches(port, headers, guard):
            raise RuntimeError('凝素列表或全部筛选未核实，停止定位')

        def located(box):
            raise entry._RewardRowLocated(box.center()[1] * 1080 / task.height)
        try:
            with entry.forgery_click_scope(task, port, headers, guard, on_selected=located):
                native_select(index, 20, [5, 5, 5, 5])
        except entry._RewardRowLocated as row:
            y = round(row.y)
        else:
            raise RuntimeError('原生选择器未被拦截，不继续')
        guard()
        port.click_cell([1483, y])
        readings = []
        for _ in range(12):
            guard()
            frame = port._frame()
            token = port._read(popup_name, frame)
            name = token.get('text') if isinstance(token, dict) else None
            score = token.get('confidence') if isinstance(token, dict) else None
            if name in all_names and type(score) in (int, float) and (0.9 <= score <= 1) and entry.matches(port, owned, guard):
                readings.append(name)
                if len(readings) == 2 and readings[0] == readings[1]:
                    break
            else:
                readings = []
            entry.pause(port, 0.15)
        else:
            raise RuntimeError('奖励材料身份未核实，保留当前画面，不进副本')
        name = readings[-1]
        guard()
        x, y_close, w, h = reference['close_roi']
        port.click_cell([round(x + w / 2), round(y_close + h / 2)])
        if not entry.wait_labels(port, headers, guard):
            raise RuntimeError('奖励弹窗关闭后未回到列表，不进副本')
        if name in expected_names:
            guard()
            return native_select(index, 20, [5, 5, 5, 5])
    raise RuntimeError('当前原生列表未找到目标材料系列，不使用旧位置兜底')
