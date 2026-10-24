from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
SPECS = {'wuwa': ('Client-Win64-Shipping.exe', '鸣潮'), 'zzz': ('ZenlessZoneZero.exe', 'ZenlessZoneZero')}
"Passive bag evidence adapter. No clicks, navigation, downloads or farming.\n\nRequires a calibrated native page anchor and item label/count ROIs. A bag must\nalready be open. Reuses OneDragon's native capture and installed CPU OCR.\n"
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path, PurePosixPath
import sys
import time
import unicodedata
from copy import deepcopy
ROOT = inventory_root()
CATEGORIES = {'currency', 'character_exp', 'character_promotion', 'weapon_exp', 'weapon_promotion', 'skill', 'core_skill_expert', 'weekly_boss'}
from src.inventory_support import inventory_observation as observation

def roi(value):
    if not isinstance(value, list) or len(value) != 4 or (not all((isinstance(n, int) and (not isinstance(n, bool)) for n in value))):
        raise ValueError('ROI requires four integers')
    x, y, w, h = value
    if x < 0 or y < 0 or w <= 0 or (h <= 0) or (x + w > 1920) or (y + h > 1080):
        raise ValueError('ROI outside calibrated 1920x1080')
    return value

def calibration(value, game):
    if not isinstance(value, dict) or value.get('schema') != 'native-bag-calibration/v1' or value.get('game') != game or (value.get('ready') is not True) or (not isinstance(value.get('native_evidence'), str)) or (not value['native_evidence']) or (not isinstance(value.get('game_version'), str)) or (not value['game_version']):
        raise ValueError('Native calibration not verified; no capture or inferred counts')
    if not isinstance(value.get('game_exe_sha256'), str) or re.fullmatch('[0-9a-fA-F]{64}', value['game_exe_sha256']) is None:
        raise ValueError('Calibration requires exact game binary fingerprint')
    if value.get('scope') != 'selected_materials_only':
        raise ValueError('Partial page must not claim complete inventory')
    resources = value.get('resource_fingerprints')
    if not isinstance(resources, dict) or not 1 <= len(resources) <= 256:
        raise ValueError('Native resource version fingerprints required')
    for relative, digest in resources.items():
        if not isinstance(relative, str) or not relative or '\\' in relative or (':' in relative) or PurePosixPath(relative).is_absolute() or ('..' in PurePosixPath(relative).parts) or (not isinstance(digest, str)) or (re.fullmatch('[0-9a-f]{64}', digest) is None):
            raise ValueError('Invalid native resource fingerprint')
    anchor = value.get('page_anchor', {})
    if not isinstance(anchor, dict):
        raise ValueError('Native page anchor not calibrated')
    roi(anchor.get('roi'))
    if not isinstance(anchor.get('text'), str) or not anchor['text'].strip():
        raise ValueError('Missing exact native page anchor')
    navigation = value.get('navigation_rois', {})
    if not isinstance(navigation, dict) or not set(navigation).issubset({'grid', 'scrollbar'}):
        raise ValueError('Only calibrated grid/scrollbar diagnostic crops allowed')
    for diagnostic_roi in navigation.values():
        roi(diagnostic_roi)
    items = value.get('materials')
    if not isinstance(items, list) or not 1 <= len(items) <= 128:
        raise ValueError('Expected 1..128 explicitly bound material entries')
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or (not item['id']) or (item['id'] in ids) or (not isinstance(item.get('name'), str)) or (not item['name'].strip()) or (item.get('category') not in CATEGORIES):
            raise ValueError('Invalid/duplicate item identity or category')
        ids.add(item['id'])
        roi(item.get('label_roi'))
        roi(item.get('quantity_roi'))
        target = item.get('target')
        if target is not None and (isinstance(target, bool) or not isinstance(target, int) or target <= 0):
            raise ValueError('Invalid editable target')
    if 'stock_anchor' in value:
        stock_anchor(value)
    return value

def load_calibration(path, game):
    """Resolve an explicit layout selection, never invent per-item evidence.

    Existing measured pages keep their format. A selection inherits ONLY
    the reviewed material-detail layout/version, plus sourced exact identities.
    It authorizes a bounded read attempt, not a confirmed quantity or new route.
    """
    path = Path(path).resolve(strict=True)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Calibration too large')
    raw = path.read_bytes()
    value = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Calibration object required')
    dependencies = {}
    if value.get('schema') == 'native-inventory-version-candidate/v1':
        from src.inventory_support import inventory_version_candidate as version_module
        value = version_module.resolve(path, value, game, 'calibration', load_calibration)
        calibration(value, game)
        return value
    if value.get('schema') == 'native-reward-popup-selection/v1':
        if set(value) != {'schema', 'game', 'ready', 'candidate_only', 'layout', 'identity'} or value.get('game') != game or value.get('ready') is not True or (value.get('candidate_only') is not True):
            raise ValueError('Explicit game-bound reward popup selection required')

        def reward_reference(binding, fields):
            if not isinstance(binding, dict) or set(binding) != fields or (not isinstance(binding.get('file'), str)) or (re.fullmatch('[A-Za-z0-9_-]+\\.json', binding['file']) is None) or (not isinstance(binding.get('sha256'), str)) or (re.fullmatch('[a-f0-9]{64}', binding['sha256']) is None):
                raise ValueError('Exact sibling reward layout/catalog reference required')
            lexical = path.parent / binding['file']
            source = lexical.resolve(strict=True)
            if source != lexical or source == path or source.stat().st_size > 1024 * 1024:
                raise ValueError('Reward reference escapes bounded sibling config scope')
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != binding['sha256']:
                raise ValueError('Reward layout/catalog changed; re-review selection')
            dependencies[str(source)] = binding['sha256']
            return json.loads(data.decode('utf-8-sig'))
        base = reward_reference(value['layout'], {'file', 'sha256'})
        if not isinstance(base, dict) or base.get('schema') != 'native-bag-calibration/v1':
            raise ValueError('Recursive/unmeasured reward layout inheritance forbidden')
        calibration(base, game)
        if base.get('candidate_only') is not True or len(base['materials']) != 1 or 'stock_anchor' not in base or (base['materials'][0]['category'] == 'currency') or (base['page_anchor']['text'] != base['materials'][0]['name']) or (base['page_anchor']['roi'] != base['materials'][0]['label_roi']):
            raise ValueError('Reviewed exact-material owned-stock popup required')
        catalog = reward_reference(value['identity'], {'file', 'sha256', 'id'})
        required = observation.required_materials(catalog, game)
        key = value['identity']['id']
        if not isinstance(key, str) or key not in required or required[key]['category'] != base['materials'][0]['category'] or (required[key]['category'] in ('currency', 'weekly_boss')):
            raise ValueError('One sourced same-category ordinary reward identity required')
        result = deepcopy(base)
        item = result['materials'][0]
        item.update(id=key, name=required[key]['name'], category=required[key]['category'])
        item.pop('target', None)
        item.pop('quantity', None)
        result['page_anchor']['text'] = item['name']
        result['native_evidence'] = 'POPUP LAYOUT ONLY, not this item: ' + base['native_evidence']
        result['recognition_basis'] = {'kind': 'inherited_reward_popup_runtime_exact_identity', 'layout_sha256': value['layout']['sha256'], 'catalog_sha256': value['identity']['sha256'], 'per_item_native_acceptance': 'unproven_before_capture'}
        value = result
    if value.get('schema') == 'native-bag-layout-selection/v1':
        if game not in ('zzz', 'wuwa') or set(value) != {'schema', 'game', 'ready', 'candidate_only', 'layout', 'identities'} or value.get('game') != game or (value.get('ready') is not True) or (value.get('candidate_only') is not True):
            raise ValueError('Explicit candidate game-bound layout selection required')

        def reference(binding, fields):
            if not isinstance(binding, dict) or set(binding) != fields or (not isinstance(binding.get('file'), str)) or (re.fullmatch('[A-Za-z0-9_-]+\\.json', binding['file']) is None) or (not isinstance(binding.get('sha256'), str)) or (re.fullmatch('[a-f0-9]{64}', binding['sha256']) is None):
                raise ValueError('Exact bounded layout/catalog reference required')
            lexical = path.parent / binding['file']
            file = lexical.resolve(strict=True)
            if file != lexical or file == path or file.stat().st_size > 1024 * 1024:
                raise ValueError('Layout reference escapes its sibling config scope')
            data = file.read_bytes()
            if hashlib.sha256(data).hexdigest() != binding['sha256']:
                raise ValueError('Layout/catalog input changed; re-review selection')
            dependencies[str(file)] = binding['sha256']
            return json.loads(data.decode('utf-8-sig'))
        base = reference(value['layout'], {'file', 'sha256'})
        if not isinstance(base, dict) or base.get('schema') != 'native-bag-calibration/v1':
            raise ValueError('Recursive/unmeasured layout inheritance forbidden')
        calibration(base, game)
        if 'stock_anchor' in base or len(base['materials']) != 1 or base['materials'][0]['category'] == 'currency':
            raise ValueError('Only the reviewed ordinary material-detail layout is reusable')
        if game == 'zzz':
            if base.get('candidate_only') is not True or base['page_anchor']['text'] != '材料道具':
                raise ValueError('Reviewed ZZZ ordinary material-detail layout required')
        elif not (base['page_anchor']['text'] == '武器' and base['materials'][0]['category'] == 'weapon_exp' or (base['page_anchor']['text'] == '资源' and base['materials'][0]['category'] in ('skill', 'weapon_promotion'))):
            raise ValueError('Only reviewed WuWa weapon EXP/resource detail layout is reusable')
        catalog = reference(value['identities'], {'file', 'sha256', 'ids'})
        required = observation.required_materials(catalog, game)
        ids = value['identities']['ids']
        if not isinstance(ids, list) or not 1 <= len(ids) <= 128 or any((not isinstance(key, str) or key not in required for key in ids)) or (len(set(ids)) != len(ids)) or (len({compact(required[key]['name']) for key in ids}) != len(ids)) or any((required[key]['category'] == 'currency' for key in ids)):
            raise ValueError('Unique sourced non-currency identities required')
        if game == 'wuwa':
            allowed = {'weapon_exp'} if base['page_anchor']['text'] == '武器' else {'skill', 'weapon_promotion'}
            if any((required[key]['category'] not in allowed for key in ids)):
                raise ValueError('WuWa tab cannot inherit other material categories')
        result = deepcopy(base)
        result['candidate_only'] = True
        template = base['materials'][0]
        result['materials'] = [dict(id=key, name=required[key]['name'], category=required[key]['category'], label_roi=deepcopy(template['label_roi']), quantity_roi=deepcopy(template['quantity_roi'])) for key in ids]
        result['reason'] = 'Inherited layout; each new identity needs fresh exact-name/count evidence at runtime.'
        result['native_evidence'] = 'LAYOUT ONLY, not these items: ' + base['native_evidence']
        result['recognition_basis'] = {'kind': 'inherited_layout_runtime_exact_identity', 'layout_sha256': value['layout']['sha256'], 'catalog_sha256': value['identities']['sha256'], 'per_item_native_acceptance': 'unproven_before_capture'}
        value = result
    calibration(value, game)
    value['_source_file_sha256'] = hashlib.sha256(raw).hexdigest()
    value['_dependency_sha256'] = dependencies
    return value

def check_calibration_sources(cfg):
    for name, digest in cfg.get('_dependency_sha256', {}).items():
        path = Path(name)
        if path.stat().st_size > 1024 * 1024 or file_sha256(path) != digest:
            raise RuntimeError('Inherited layout/catalog changed; no capture or further input')

def stock_anchor(value):
    """A reward tooltip needs explicit *owned* stock, not a drop preview.

    The label must sit immediately left of the count on the same row. This
    optional binding is independently checked in capture and offline replay.
    It cannot be used to accept another item's count elsewhere in a dialog.
    """
    anchor = value.get('stock_anchor')
    items = value.get('materials', [])
    if not isinstance(anchor, dict) or set(anchor) != {'text', 'roi'} or anchor.get('text') not in ('持有', '拥有', '持有数量', '当前拥有', '已拥有') or (len(items) != 1) or (value.get('candidate_only') is not True):
        raise ValueError('Owned-stock popup requires one reviewed item and exact owned label')
    x, y, w, h = roi(anchor.get('roi'))
    qx, qy, qw, qh = roi(items[0].get('quantity_roi'))
    if not (x + w <= qx <= x + w + 80 and qx + qw - x <= 500 and (abs(y + h / 2 - qy - qh / 2) <= min(h, qh) / 2)):
        raise ValueError('Owned-stock label is not bound to its adjacent quantity')
    return anchor

def compact(text):
    return ''.join(unicodedata.normalize('NFKC', text).split())

def bound_result(matches, expected=None):
    if len(matches) != 1:
        return None
    match = matches[0]
    if not isinstance(match.data, str):
        return None
    if not 0.9 <= match.confidence <= 1:
        return None
    identity = lambda text: compact(text).replace('強', '强')
    if expected is not None and identity(match.data) != identity(expected):
        return None
    return match

def owned_window(windows, pid, caption):
    matches = [w for w in windows if w['pid'] == pid and w['visible'] is True and (w['title'].strip() == caption)]
    if len(matches) != 1:
        raise RuntimeError('Expected one visible window owned by verified game PID')
    return matches[0]

def capture_slots(frames):
    """At most six passive attempts; accepted frames keep contiguous IDs."""
    for sample in range(6):
        if len(frames) >= 2:
            return
        yield (sample, len(frames))

def verified_pair(frames):
    return len(frames) == 2 and all((f.get('page_verified') is True for f in frames))

def atomic_json(path, value):
    staged = path.with_suffix(path.suffix + '.tmp')
    try:
        staged.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)

def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def native_resource_fingerprints(game, executable):
    if game == 'zzz':
        base = executable.parent
        persistent = base / 'ZenlessZoneZero_Data/Persistent'
        files = [persistent / name for name in ('base_version_hash', 'op_version', 'data_version_persist', 'res_version_persist', 'silence_version_persist')]
    elif game == 'wuwa':
        base = executable.parents[2]
        files = sorted((base / 'Saved/Resources').glob('*/ResManifest/*'))
        files = [file for file in files if file.is_file()]
    else:
        raise ValueError('Unsupported resource catalog')
    if not 1 <= len(files) <= 256 or any((not file.is_file() for file in files)):
        raise RuntimeError('Native resource version catalog unavailable')
    return {file.relative_to(base).as_posix(): file_sha256(file) for file in files}
