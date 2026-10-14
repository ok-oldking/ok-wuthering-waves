from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Bounded read-only bag search, shared by future native assistant ports.

No Windows input backend lives here. Ports must reuse their assistant's capture,
OCR and controller. Geometry stays disabled until evidenced in the native bag.
This module selects details; it never uses, discards, merges or purchases items.
"""
from math import isfinite
import importlib.util
from pathlib import Path
import re
import time
from src.inventory_support import inventory_native_probe as probe
from src.inventory_support import inventory_scrollbar as scrollbar
from src.inventory_support import inventory_entry_navigation as entry_navigation
from src.inventory_support import inventory_zzz_entry_navigation as zzz_entry_navigation

def entry_module(page):
    return zzz_entry_navigation if page.get('game') == 'zzz' else entry_navigation

def validated_viewport_cells(tab, cells):
    """Allow only the reviewed weapon lattice, never arbitrary port clicks."""
    failure = 'Native viewport cells are not a nonempty calibrated subset'
    footer = tab.get('selection_policy') == 'exclude_confirmed_weapon_level_footers'
    if not isinstance(cells, list) or (not cells and (not footer)) or any((not isinstance(cell, list) or len(cell) != 2 or any((type(n) is not int for n in cell)) for cell in cells)):
        raise ValueError(failure)
    if len({tuple(cell) for cell in cells}) != len(cells):
        raise ValueError(failure)
    if all((cell in tab['cells'] for cell in cells)):
        return cells
    columns = sorted({cell[0] for cell in tab['cells']})
    reviewed = [[x, y] for y in (225, 435, 645) for x in columns]
    if not footer or tab.get('scroll_mode') != 'native_grid_wheel' or tab.get('start_endpoint', 'top') != 'top' or (len(columns) != 6) or (sorted(tab['cells']) != sorted(reviewed)) or (len(cells) > 18):
        raise ValueError(failure)
    ys = sorted({cell[1] for cell in cells})
    x0, y0, width, height = tab['grid_roi']
    if any((x not in columns or not 225 <= y <= 821 or (not x0 <= x < x0 + width) or (not y0 <= y < y0 + height) for x, y in cells)) or len(ys) > 3 or ys[-1] - ys[0] > 420 or any(((y - ys[0]) % 210 for y in ys)):
        raise ValueError(failure)
    return cells

def currency_popup_route(page, tab):
    """Exact ordinary-currency allowlist; geometry must come from calibration."""
    probe.calibration(page, page.get('game'))
    identity = {'wuwa': ('shell-credit', '贝币', '资源'), 'zzz': ('denny', '丁尼', '材料道具')}.get(page['game'])
    if identity is None or (page['game'] == 'zzz' and page.get('candidate_only') is not True):
        raise ValueError('Read-only currency popup requires an explicit reviewed candidate')
    item_id, name, base_name = identity
    if len(page['materials']) != 1 or page['materials'][0]['category'] != 'currency' or page['materials'][0]['id'] != item_id or (probe.compact(page['materials'][0]['name']) != name) or (probe.compact(page['page_anchor']['text']) != name) or (page['materials'][0]['label_roi'] != page['page_anchor']['roi']):
        raise ValueError('Read-only currency popup must bind one exact currency label')
    if not isinstance(tab, dict) or set(tab) != {'strategy', 'base_page_anchor', 'base_tab_roi', 'open_roi'} or tab['strategy'] != 'readonly_currency_popup':
        raise ValueError('Currency popup route cannot contain grid or extra input operations')
    base = tab['base_page_anchor']
    if not isinstance(base, dict) or set(base) != {'text', 'roi'} or base.get('text') != base_name:
        raise ValueError('Currency popup requires verified native resource bag base')
    probe.roi(base['roi'])
    probe.roi(tab['base_tab_roi'])
    probe.roi(tab['open_roi'])
    return tab

def reward_popup_route(page, tab):
    """Read-only candidate at an ALREADY OPEN material entry, never combat.

    No route may include start, purchase, confirm or farming actions. Geometry
    and two entry labels must be reviewed on this version. Optional transport
    is a strictly reviewed native book prefix, never full teleport-to-battle.
    """
    probe.calibration(page, page.get('game'))
    probe.stock_anchor(page)
    if len(page['materials']) != 1 or probe.compact(page['page_anchor']['text']) != probe.compact(page['materials'][0]['name']) or page['page_anchor']['roi'] != page['materials'][0]['label_roi']:
        raise ValueError('Reward popup must bind one exact material and owned stock')
    fields = {'strategy', 'material_id', 'entry_anchors', 'open_roi', 'close_roi'}
    if not isinstance(tab, dict) or set(tab) not in (fields, fields | {'entry_navigation'}) or tab.get('strategy') != 'readonly_reward_popup' or (tab['material_id'] != page['materials'][0]['id']):
        raise ValueError('Reward popup cannot contain extra input or another material identity')
    anchors = tab['entry_anchors']
    if not isinstance(anchors, list) or not 2 <= len(anchors) <= 3 or any((not isinstance(a, dict) or set(a) != {'text', 'roi'} or (not isinstance(a.get('text'), str)) or (not 1 <= len(a['text'].strip()) <= 64) for a in anchors)) or (len({a['text'] for a in anchors}) != len(anchors)):
        raise ValueError('Reward entry requires two distinct reviewed native labels')
    for anchor in anchors:
        probe.roi(anchor['roi'])
    probe.roi(tab['open_roi'])
    probe.roi(tab['close_roi'])
    if tab['open_roi'] == tab['close_roi']:
        raise ValueError('Opening and closing the reward popup cannot be the same action')
    if 'entry_navigation' in tab:
        entry_module(page).validate(page, tab['entry_navigation'])
    return tab

def reward_popup_action(port, page, route, guard, *, close=False):
    """One native click and finite observations; unknown screen sends no input.

    Reuses both assistants' existing guarded frame/OCR/click primitives. The
    caller must already own the native entry. This never assumes a click
    succeeded and never toggles a second time on slow animations.
    """
    reward_popup_route(page, route)
    descriptor = route.get('entry_navigation', {})
    if not close and descriptor.get('strategy') in ('wuwa_forgery_book', 'wuwa_forgery_reward_list'):
        entry_navigation.verify_forgery_selector(getattr(port, 'task', None))
    pause = getattr(port, 'pause', None)
    if not callable(pause):
        pause = port.task.sleep
    if not all((callable(getattr(port, key, None)) for key in ('_frame', '_read', 'click_cell'))):
        raise ValueError('Native popup capture/OCR/input adapter unavailable')

    def matches(anchors):
        for index in range(2):
            guard()
            frame = port._frame()
            for anchor in anchors:
                guard()
                token = port._read(anchor['roi'], frame)
                if not exact_detail(token, {'name': anchor['text']}):
                    return False
            guard()
            if index == 0:
                pause(0.15)
        return True
    popup = [page['page_anchor'], probe.stock_anchor(page)]
    present = matches(popup)
    if not close and present:
        return True
    if not close and descriptor.get('strategy') == 'wuwa_forgery_reward_list':
        return entry_navigation.open_forgery_reward(port, page, descriptor, route['entry_anchors'], popup, guard)
    if close:
        if not present:
            return False
    elif not matches(route['entry_anchors']):
        descriptor = route.get('entry_navigation')
        if descriptor is None or entry_module(page).navigate(port, page, descriptor, route['entry_anchors'], guard) is not True:
            return False
        if not matches(route['entry_anchors']):
            return False
    for field in ('scrollbar', 'selected_thumb', 'selection_policy'):
        if hasattr(port, field):
            setattr(port, field, None)
    guard()
    x, y, w, h = route['close_roi' if close else 'open_roi']
    port.click_cell([round(x + w / 2), round(y + h / 2)])
    guard()
    for _ in range(12):
        pause(0.2)
        guard()
        if close:
            if matches(route['entry_anchors']) and (not matches(popup)):
                return True
        elif matches(popup):
            return True
    return False

def navigation_calibration(value, page):
    probe.calibration(page, page.get('game'))
    if not isinstance(value, dict) or value.get('schema') != 'native-inventory-navigation/v1' or value.get('game') != page['game'] or (value.get('ready') is not True) or (not isinstance(value.get('native_evidence'), str)) or (not value['native_evidence']) or (value.get('game_exe_sha256') != page['game_exe_sha256']) or (value.get('resource_fingerprints') != page['resource_fingerprints']):
        raise ValueError('Native navigation calibration/version not verified')
    tabs = value.get('tabs')
    anchor = page['page_anchor']['text']
    if not isinstance(tabs, dict) or anchor not in tabs:
        raise ValueError('Selected bag tab not calibrated')
    tab = tabs[anchor]
    if not isinstance(tab, dict):
        raise ValueError('Invalid selected tab')
    if tab.get('strategy') == 'readonly_reward_popup':
        if value.get('candidate_only') is not True:
            raise ValueError('Reward popup navigation requires explicit reviewed candidate')
        return reward_popup_route(page, tab)
    if tab.get('strategy') == 'readonly_currency_popup':
        if page['game'] == 'zzz' and value.get('candidate_only') is not True:
            raise ValueError('ZZZ currency navigation remains candidate-only')
        return currency_popup_route(page, tab)
    if any((item['category'] == 'currency' for item in page['materials'])):
        raise ValueError('Currency requires an exact read-only popup route, never a fake grid')
    if tab.get('strategy', 'grid') != 'grid':
        raise ValueError('Unsupported native inventory navigation strategy')
    probe.roi(tab.get('grid_roi'))
    probe.roi(tab.get('tab_roi'))
    cells = tab.get('cells')
    if not isinstance(cells, list) or not 1 <= len(cells) <= 80:
        raise ValueError('Expected 1..80 native grid cells')
    x, y, w, h = tab['grid_roi']
    seen = set()
    for cell in cells:
        if not isinstance(cell, list) or len(cell) != 2 or any((type(n) is not int for n in cell)) or (tuple(cell) in seen) or (not x <= cell[0] < x + w) or (not y <= cell[1] < y + h):
            raise ValueError('Cell outside native read-only grid or duplicate')
        seen.add(tuple(cell))
    if type(tab.get('scroll_notches')) is not int or not 1 <= tab['scroll_notches'] <= 6:
        raise ValueError('Expected bounded forward scroll')
    if type(tab.get('max_pages')) is not int or not 1 <= tab['max_pages'] <= 20:
        raise ValueError('Expected 1..20 page limit')
    if type(tab.get('max_reset_pages')) is not int or not 2 <= tab['max_reset_pages'] <= 20:
        raise ValueError('Expected bounded native scroll-to-top calibration')
    if type(tab.get('max_clicks')) is not int or not 1 <= tab['max_clicks'] <= 240:
        raise ValueError('Expected 1..240 click limit')
    mode = tab.get('scroll_mode', 'wheel')
    if mode not in ('wheel', 'native_track_click', 'native_grid_wheel'):
        raise ValueError('Uncalibrated inventory scroll strategy')
    if mode in ('native_track_click', 'native_grid_wheel'):
        if page['game'] not in ('wuwa', 'zzz') or (page['game'] == 'zzz' and mode != 'native_grid_wheel'):
            raise ValueError('Scrollbar-assisted navigation not calibrated for this game')
        scrollbar.validate(tab.get('scrollbar'))
    elif 'scrollbar' in tab:
        raise ValueError('Scrollbar geometry requires explicit native track mode')
    endpoint = tab.get('start_endpoint', 'top')
    if endpoint not in ('top', 'bottom'):
        raise ValueError('Unsupported native search endpoint')
    if endpoint == 'bottom':
        if value.get('candidate_only') is not True or page['game'] != 'wuwa' or anchor != '武器' or (mode != 'native_grid_wheel') or any((item['category'] != 'weapon_exp' for item in page['materials'])) or (type(tab.get('bottom_max_gap')) is not int) or (not 0 <= tab['bottom_max_gap'] <= 30) or ('selection_policy' in tab):
            raise ValueError('Bottom search requires candidate weapon EXP native calibration')
    elif 'bottom_max_gap' in tab:
        raise ValueError('Bottom tolerance requires explicit bottom search')
    if 'endpoint_seek' in tab and (value.get('candidate_only') is not True or page['game'] != 'wuwa' or mode != 'native_grid_wheel' or (tab['endpoint_seek'] != 'bounded_native_wheel')):
        raise ValueError('Endpoint seek requires candidate WuWa native wheel calibration')
    if 'selection_policy' in tab:
        if tab['selection_policy'] == 'exclude_confirmed_weapon_level_footers':
            if value.get('candidate_only') is not True or page['game'] != 'wuwa' or anchor != '武器' or (mode != 'native_grid_wheel') or (endpoint != 'top') or any((item['category'] != 'weapon_exp' for item in page['materials'])):
                raise ValueError('Footer exclusion requires candidate TOP weapon EXP calibration')
        elif page['game'] != 'zzz' or mode != 'native_grid_wheel' or tab['selection_policy'] != 'interior_rows_with_endpoint_edges' or (tab['scroll_notches'] != 1):
            raise ValueError('Endpoint-aware selection requires native ZZZ grid and one-step overlap')
        rows = sorted({cell[1] for cell in cells})
        columns = {cell[0] for cell in cells}
        expected_rows = 3 if tab['selection_policy'] == 'exclude_confirmed_weapon_level_footers' else 4
        if len(rows) != expected_rows or len(columns) < 2 or len(cells) != expected_rows * len(columns):
            raise ValueError('Endpoint-aware selection requires a complete four-row calibrated grid')
    return tab

def exact_detail(observation, material):
    if not isinstance(observation, dict):
        return False
    score = observation.get('confidence')
    return isinstance(observation.get('text'), str) and probe.compact(observation['text']) == probe.compact(material['name']) and (not isinstance(score, bool)) and isinstance(score, (int, float)) and isfinite(score) and (0.9 <= score <= 1)

def detail_diagnostic(token):
    """Bounded bag-label evidence only; never a count or accepted identity."""
    if not isinstance(token, dict):
        return {'text': None, 'confidence': None}
    text, score = (token.get('text'), token.get('confidence'))
    valid_score = not isinstance(score, bool) and isinstance(score, (int, float)) and isfinite(score) and (0 <= score <= 1)
    return {'text': text[:128] if isinstance(text, str) else None, 'confidence': score if valid_score else None}

def batch_selection(selections, manifest):
    """Validate one shared native grid before any input, never infer counts."""
    if not isinstance(selections, list) or not 1 <= len(selections) <= 128:
        raise ValueError('Expected 1..128 explicit batch selections')
    bound, ids, names, binding = ([], set(), set(), None)
    for entry in selections:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError('Batch selection requires page and material identity')
        page, item_id = entry
        tab = navigation_calibration(manifest, page)
        if tab.get('strategy') in ('readonly_currency_popup', 'readonly_reward_popup'):
            raise ValueError('Popup cannot be scanned as a shared material grid')
        item = next((row for row in page['materials'] if row['id'] == item_id), None)
        if item is None:
            raise ValueError('Batch material not bound to calibrated detail')
        name = probe.compact(item['name'])
        if item_id in ids or name in names:
            raise ValueError('Ambiguous or duplicate batch material')
        ids.add(item_id)
        names.add(name)
        current = (page['game'], page['game_exe_sha256'], page['resource_fingerprints'], page['page_anchor'], tab, item['label_roi'])
        if binding is not None and binding != current:
            raise ValueError('Single pass requires one grid and bound detail-label ROI')
        binding = current
        bound.append((page, item))
    return (bound, tab)

def reward_checkpoint_binding(page, route):
    """A native destination, not one material or one screen coordinate.

    Sibling qualities may share an entry, but never a currency, another boss,
    version, filter or close operation. The exact per-item popup check remains
    mandatory. This only batches already configured/validated read attempts.
    """
    reward_popup_route(page, route)
    descriptor = route.get('entry_navigation')
    destination = None
    if descriptor is not None:
        index = entry_module(page).validate(page, descriptor)
        if descriptor.get('strategy') == 'wuwa_forgery_reward_list':
            family = entry_navigation.FORGERY_REWARDS[page['materials'][0]['id']][2]
            destination = (index, family)
        elif descriptor.get('strategy') == 'zzz_simulation_preview':
            destination = tuple(index[2:])
        else:
            destination = index
    return (page['game'], page['game_exe_sha256'], page['resource_fingerprints'], descriptor, destination, route['entry_anchors'], route['close_roi'])

def scan_reward_checkpoint(port, selections, manifest, guard, capture, *, budget_seconds=180, clock=time.monotonic, event=lambda *args: None):
    """Shared native-entry checkpoint: open/read/close each sibling material.

    Uses the existing native preview and guarded popup primitives. Never calls
    the battle graph, card-count selection, deploy, claim or refill. No stock is
    inferred from a successful click. capture owns the fresh exact-count proof.
    All siblings are preflighted before the first observation/input.
    """
    if not isinstance(selections, list) or not 1 <= len(selections) <= 4 or type(budget_seconds) is not int or (not 1 <= budget_seconds <= 600) or (not all((callable(fn) for fn in (guard, capture, clock, event)))):
        raise ValueError('Expected one bounded checkpoint of1..4 sibling rewards')
    binding, ids, routes = (None, set(), [])
    for entry in selections:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError('Checkpoint requires page and material identity')
        page, item_id = entry
        route = navigation_calibration(manifest, page)
        if route.get('strategy') != 'readonly_reward_popup' or len(page['materials']) != 1 or page['materials'][0]['id'] != item_id or (item_id in ids):
            raise ValueError('Checkpoint requires unique exact reward-popup identities')
        ids.add(item_id)
        current = reward_checkpoint_binding(page, route)
        if binding is not None and current != binding:
            raise ValueError('Checkpoint cannot mix native destinations or versions')
        binding = current
        routes.append(route)
    deadline, found = (clock() + budget_seconds, [])

    def check():
        guard()
        if clock() >= deadline:
            raise TimeoutError('Native reward checkpoint budget exhausted')
    for index, ((page, item_id), route) in enumerate(zip(selections, routes)):
        check()
        event('reward_checkpoint_material_started', {'index': index, 'material': item_id})
        remaining = max(1, int(deadline - clock()))
        if find_selected_detail(port, page, manifest, check, material_id=item_id, budget_seconds=min(180, remaining), clock=clock, event=event) is not True:
            return found
        try:
            check()
            capture(index)
            check()
        except Exception:
            check()
            if reward_popup_action(port, page, route, check, close=True) is not True:
                raise RuntimeError('Reward popup cleanup unverified after capture failure')
            raise
        if reward_popup_action(port, page, route, check, close=True) is not True:
            raise RuntimeError('Reward popup cleanup unverified; session incomplete')
        check()
        found.append(index)
        event('reward_popup_closed', {'index': index})
    return found

def grouped_selection(selections, manifest):
    """Preflight all routes; visit each grid once, retain original report indices.

    Read-only inspection order is first appearance of a route, not farming
    priority. Nonadjacent selections with identical bindings share a traversal.
    Currency popups remain separate and never become grid selections.
    """
    if not isinstance(selections, list) or not 1 <= len(selections) <= 128:
        raise ValueError('Expected 1..128 explicit grouped selections')
    groups, seen, names, version = ([], set(), set(), None)
    for index, entry in enumerate(selections):
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError('Grouped selection requires page and material identity')
        page, item_id = entry
        tab = navigation_calibration(manifest, page)
        item = next((row for row in page['materials'] if row['id'] == item_id), None)
        if item is None or item_id in seen or probe.compact(item['name']) in names:
            raise ValueError('Unbound or duplicate grouped material')
        seen.add(item_id)
        names.add(probe.compact(item['name']))
        current_version = (page['game'], page['game_exe_sha256'], page['resource_fingerprints'])
        if version is not None and version != current_version:
            raise ValueError('Mixed grouped native versions')
        version = current_version
        strategy = tab.get('strategy')
        currency = strategy in ('readonly_currency_popup', 'readonly_reward_popup')
        binding = reward_checkpoint_binding(page, tab) if strategy == 'readonly_reward_popup' else (page['page_anchor'], tab, item['label_roi'])
        if strategy == 'readonly_reward_popup':
            matching = groups[-1] if groups and groups[-1]['kind'] == 'reward' and (groups[-1]['binding'] == binding) and (len(groups[-1]['indices']) < 4) else None
        else:
            matching = next((group for group in groups if not currency and group['kind'] == 'grid' and (group['binding'] == binding)), None)
        if matching is not None:
            matching['indices'].append(index)
        else:
            groups.append({'kind': 'reward' if strategy == 'readonly_reward_popup' else 'currency' if currency else 'grid', 'binding': binding, 'indices': [index]})
    for group in groups:
        if group['kind'] == 'grid':
            batch_selection([selections[i] for i in group['indices']], manifest)
    return groups

def scan_grouped_details(port, selections, manifest, guard, capture, *, budget_seconds=180, clock=time.monotonic, event=lambda *args: None):
    """One shared deadline; immediate captures with original plan indices."""
    groups = grouped_selection(selections, manifest)
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 600 or (not callable(capture)):
        raise ValueError('Bounded grouped budget and capture callback required')
    deadline, found = (clock() + budget_seconds, [])

    def check():
        guard()
        if clock() >= deadline:
            raise TimeoutError('Native grouped inventory budget exhausted')

    def capture_original(index):
        check()
        if index in found:
            raise ValueError('Duplicate grouped capture')
        capture(index)
        check()
        found.append(index)
    last_grid = None
    for group in groups:
        check()
        indices = group['indices']
        remaining = int(deadline - clock())
        if remaining < 1:
            raise TimeoutError('No remaining grouped navigation budget')
        event('group_navigation_started', {'kind': group['kind'], 'indices': indices})
        if group['kind'] in ('currency', 'reward'):
            index = indices[0]
            page, item_id = selections[index]
            route = navigation_calibration(manifest, page)
            direct_forgery = group['kind'] == 'reward' and route.get('entry_navigation', {}).get('strategy') == 'wuwa_forgery_reward_list'
            if direct_forgery and last_grid is not None:
                if entry_navigation.leave_verified_menu(port, check, bag_page=last_grid) is not True:
                    raise RuntimeError('Known bag cleanup unverified; no guidebook input')
                last_grid = None
            if group['kind'] == 'reward':
                captured = scan_reward_checkpoint(port, [selections[i] for i in indices], manifest, check, lambda local: capture_original(indices[local]), budget_seconds=min(600, remaining), clock=clock, event=lambda name, data: event(name, dict(data, index=indices[data['index']]) if 'index' in data else data))
                if captured != list(range(len(indices))):
                    return found
                if direct_forgery:
                    if entry_navigation.leave_verified_menu(port, check, labels=route['entry_anchors']) is not True:
                        raise RuntimeError('Known guidebook cleanup unverified; no bag input')
                    event('guidebook_closed', {'indices': indices})
                continue
            if find_selected_detail(port, page, manifest, check, material_id=item_id, budget_seconds=min(180, remaining), clock=clock, event=event) is not True:
                return found
            capture_original(index)
            close_popup = getattr(port, 'close_currency_popup', None)
            if callable(close_popup):
                check()
                route = navigation_calibration(manifest, page)
                if close_popup(page, route) is not True:
                    raise RuntimeError('Currency popup cleanup unverified; session incomplete')
                check()
                event('currency_popup_closed', {'index': index})
        else:
            scanned = scan_selected_details(port, [selections[i] for i in indices], manifest, check, lambda local: capture_original(indices[local]), budget_seconds=remaining, clock=clock, event=event)
            if set(scanned) != set(range(len(indices))):
                return found
            last_grid = selections[indices[scanned[-1]]]
        check()
    return found

def scan_selected_details(port, selections, manifest, guard, capture, *, budget_seconds=180, clock=time.monotonic, event=lambda *args: None):
    """One top reset, one traversal, capture immediately on each exact match.

    capture(index) runs the guarded passive collector while this detail is still
    selected. A partial return is NOT inventory completeness or zero stock.
    Its caller must retain unknowns and may not publish a successful transaction
    unless all configured selections were captured. Collector time is budgeted.
    """
    bound, tab = batch_selection(selections, manifest)
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 600 or (not callable(capture)):
        raise ValueError('Bounded batch budget and capture callback required')
    page, _ = bound[0]
    deadline = clock() + budget_seconds
    found, visited, clicks, unchanged = ([], set(), 0, 0)

    def check():
        guard()
        if clock() >= deadline:
            raise TimeoutError('Native batch inventory budget exhausted')

    def action(method, *args):
        check()
        value = method(*args)
        check()
        return value
    if action(port.bag_open) is not True and action(port.open_bag) is not True:
        event('batch_bag_not_open', {})
        return found
    if action(port.select_tab, page, tab['tab_roi']) is not True:
        event('batch_category_not_ready', {'stage': 'select_tab', 'page': page['page_anchor']['text']})
        return found
    if action(port.page_verified, page) is not True:
        event('batch_category_not_ready', {'stage': 'verify_page', 'page': page['page_anchor']['text']})
        return found
    geometry = tab.get('scroll_mode') in ('native_track_click', 'native_grid_wheel')
    if geometry:
        action(port.configure_scrollbar, tab['scrollbar'])
        if tab['scroll_mode'] == 'native_grid_wheel':
            action(port.configure_scroll_mode, 'native_grid_wheel')
        if 'selection_policy' in tab:
            action(port.configure_selection_policy, tab['selection_policy'])

    def signature():
        value = action(port.grid_signature, tab['grid_roi'])
        if not isinstance(value, str) or re.fullmatch('[a-f0-9]{64}', value) is None:
            raise ValueError('Native batch grid signature unavailable')
        return value
    stable = 0
    bottom = tab.get('start_endpoint', 'top') == 'bottom'
    reset_direction = 1 if bottom else -1
    already_top = page['game'] == 'wuwa' and geometry and (not bottom) and (action(port.at_top) is True)
    for _ in range(0 if already_top else tab['max_reset_pages']):
        if action(port.page_verified, page) is not True:
            return found
        before = signature()
        if 'endpoint_seek' in tab:
            action(port.scroll_grid, tab['grid_roi'], reset_direction * tab['scroll_notches'], True)
        else:
            action(port.scroll_grid, tab['grid_roi'], reset_direction * tab['scroll_notches'])
        stable = stable + 1 if signature() == before else 0
        if stable >= 2:
            break
    else:
        if not already_top:
            event('batch_bottom_not_verified' if bottom else 'batch_top_not_verified', {})
            return found
    endpoint_ok = action(port.at_bottom, tab['bottom_max_gap']) if bottom else action(port.at_top) if geometry else True
    if endpoint_ok is not True:
        event('batch_bottom_endpoint_unverified' if bottom else 'batch_top_endpoint_unverified', {})
        return found
    for page_index in range(tab['max_pages']):
        if action(port.page_verified, page) is not True:
            return found
        before = signature()
        event('batch_page_observed', {'page': page_index, 'grid_signature': before})
        cells = action(port.viewport_cells, tab['cells']) if 'selection_policy' in tab else tab['cells']
        cells = validated_viewport_cells(tab, cells)
        for cell in cells:
            if clicks >= tab['max_clicks']:
                event('batch_click_limit', {'clicks': clicks, 'found': len(found)})
                return found
            if action(port.page_verified, page) is not True:
                return found
            action(port.click_cell, cell)
            clicks += 1
            token = action(port.read_detail, bound[0][1]['label_roi'])
            event('batch_detail_observed', {'page': page_index, 'clicks': clicks, 'cell': list(cell), **detail_diagnostic(token)})
            matched = next((index for index, (_, item) in enumerate(bound) if index not in found and exact_detail(token, item)), None)
            if matched is not None:
                action(capture, matched)
                if action(port.page_verified, page) is not True:
                    raise RuntimeError('Native page changed during batch capture')
                found.append(matched)
                event('batch_detail_captured', {'material': bound[matched][1]['id'], 'page': page_index, 'clicks': clicks})
                if len(found) == len(bound):
                    return found
        visited.add(before)
        if page_index + 1 >= tab['max_pages']:
            break
        if action(port.page_verified, page) is not True:
            return found
        action(port.scroll_grid, tab['grid_roi'], -reset_direction * tab['scroll_notches'])
        after = signature()
        unchanged = unchanged + 1 if after == before else 0
        if unchanged >= 2 or (after != before and after in visited):
            event('batch_list_end_or_cycle', {'clicks': clicks, 'found': len(found)})
            return found
    event('batch_not_located_bounded', {'clicks': clicks, 'found': len(found)})
    return found

def find_selected_detail(port, page, manifest, guard, *, material_id=None, budget_seconds=60, clock=time.monotonic, event=lambda *args: None):
    """Search only validated cells; absence is 'not located', never stock=0.

    port.page_verified(page) must verify native bag anchor on two new frames.
    port.open_bag() may only open a bag from a confirmed world; no login/start.
    Every port action must refresh capture and be bounded/cancellable itself.
    guard checks the assistant lane, exact process/version, pause/stop and budget.
    Cropped grid hashes exclude detail selection so unchanged pages can stop.
    """
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 180:
        raise ValueError('Search budget must be 1..180 seconds')
    tab = navigation_calibration(manifest, page)
    materials = page['materials']
    selected = materials[0] if material_id is None else next((item for item in materials if item['id'] == material_id), None)
    if selected is None:
        raise ValueError('Selected material not bound to this native detail')
    deadline = clock() + budget_seconds
    clicks, unchanged, visited = (0, 0, set())

    def check():
        guard()
        if clock() >= deadline:
            raise TimeoutError('Native inventory search budget exhausted')

    def action(method, *args):
        check()
        result = method(*args)
        check()
        return result
    if tab.get('strategy') == 'readonly_reward_popup':
        found = reward_popup_action(port, page, tab, check)
        event('reward_popup_located' if found else 'reward_popup_unverified', {'material': selected['id']})
        return found
    if tab.get('strategy') == 'readonly_currency_popup':
        if action(port.open_currency_popup, page, tab) is not True:
            event('currency_popup_not_verified', {'material': selected['id']})
            return False
        if action(port.page_verified, page) is not True or not exact_detail(action(port.read_detail, selected['label_roi']), selected):
            event('currency_popup_identity_unverified', {'material': selected['id']})
            return False
        event('currency_popup_located', {'material': selected['id']})
        return True
    if action(port.bag_open) is not True and action(port.open_bag) is not True:
        event('bag_not_open', {'material': selected['id']})
        return False
    if action(port.select_tab, page, tab['tab_roi']) is not True:
        return False
    if action(port.page_verified, page) is not True:
        event('native_tab_unverified', {'material': selected['id']})
        return False
    if tab.get('scroll_mode') in ('native_track_click', 'native_grid_wheel'):
        action(port.configure_scrollbar, tab['scrollbar'])
        if tab['scroll_mode'] == 'native_grid_wheel':
            action(port.configure_scroll_mode, 'native_grid_wheel')
        if 'selection_policy' in tab:
            action(port.configure_selection_policy, tab['selection_policy'])
    top_stable = 0
    bottom = tab.get('start_endpoint', 'top') == 'bottom'
    reset_direction = 1 if bottom else -1
    already_top = page['game'] == 'wuwa' and (not bottom) and (tab.get('scroll_mode') in ('native_track_click', 'native_grid_wheel')) and (action(port.at_top) is True)
    for _ in range(0 if already_top else tab['max_reset_pages']):
        if action(port.page_verified, page) is not True:
            return False
        before = action(port.grid_signature, tab['grid_roi'])
        if 'endpoint_seek' in tab:
            action(port.scroll_grid, tab['grid_roi'], reset_direction * tab['scroll_notches'], True)
        else:
            action(port.scroll_grid, tab['grid_roi'], reset_direction * tab['scroll_notches'])
        after = action(port.grid_signature, tab['grid_roi'])
        if any((not isinstance(value, str) or re.fullmatch('[a-f0-9]{64}', value) is None for value in (before, after))):
            raise ValueError('Native scroll-to-top signature unavailable')
        top_stable = top_stable + 1 if after == before else 0
        if top_stable >= 2:
            break
    else:
        if not already_top:
            event('bottom_not_verified' if bottom else 'top_not_verified', {'material': selected['id']})
            return False
    endpoint_ok = action(port.at_bottom, tab['bottom_max_gap']) if bottom else action(port.at_top) if tab.get('scroll_mode') in ('native_track_click', 'native_grid_wheel') else True
    if endpoint_ok is not True:
        event('native_bottom_endpoint_unverified' if bottom else 'native_top_endpoint_unverified', {'material': selected['id']})
        return False
    for page_index in range(tab['max_pages']):
        if action(port.page_verified, page) is not True:
            return False
        before = action(port.grid_signature, tab['grid_roi'])
        if not isinstance(before, str) or re.fullmatch('[a-f0-9]{64}', before) is None:
            raise ValueError('Native grid signature unavailable')
        cells = action(port.viewport_cells, tab['cells']) if 'selection_policy' in tab else tab['cells']
        cells = validated_viewport_cells(tab, cells)
        for cell in cells:
            if clicks >= tab['max_clicks']:
                event('click_limit', {'material': selected['id'], 'clicks': clicks})
                return False
            if action(port.page_verified, page) is not True:
                return False
            action(port.click_cell, cell)
            clicks += 1
            detail = action(port.read_detail, selected['label_roi'])
            if exact_detail(detail, selected):
                event('detail_located', {'material': selected['id'], 'page': page_index, 'clicks': clicks})
                return True
        visited.add(before)
        if page_index + 1 >= tab['max_pages']:
            break
        if action(port.page_verified, page) is not True:
            return False
        action(port.scroll_grid, tab['grid_roi'], -reset_direction * tab['scroll_notches'])
        after = action(port.grid_signature, tab['grid_roi'])
        if not isinstance(after, str) or re.fullmatch('[a-f0-9]{64}', after) is None:
            raise ValueError('Native scrolled grid signature unavailable')
        unchanged = unchanged + 1 if after == before else 0
        if unchanged >= 2 or (after != before and after in visited):
            event('list_end_or_cycle', {'material': selected['id'], 'clicks': clicks})
            return False
    event('not_located_bounded', {'material': selected['id'], 'clicks': clicks})
    return False
