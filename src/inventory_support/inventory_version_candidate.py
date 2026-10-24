from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Explicit, pinned hot-update read trial; never relabel old native evidence.

Only additive resource-manifest updates with an unchanged binary are eligible.
Every old resource must still match. UI compatibility is UNKNOWN until capture.
This is not an automatic update policy or a farming authorization.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
SCHEMA = 'native-inventory-version-candidate/v1'
COMPOSITION = 'native-inventory-navigation-composition/v1'
RESOURCE_ITEMS = {'weapon-skill-dieyipianzhenti': ('叠翼偏振体', 'weapon_promotion'), 'promotion-refined-ring': ('改造镣环', 'character_promotion'), 'skill-duanxudexianxian': ('断续的弦线', 'skill'), 'skill-rugedexianxian': ('如歌的弦线', 'skill'), 'weekly-boss-tianquliulizhixin': ('天衢琉璃之心', 'weekly_boss'), **{f'character-exp-{q}': (n + '共鸣促剂', 'character_exp') for q, n in [('basic', '初级'), ('medium', '中级'), ('advanced', '高级'), ('premium', '特级')]}}

def compose_navigation(path, value, dependencies):
    """Combine pinned historical routes, not their native acceptance claims."""
    if set(value) != {'schema', 'game', 'candidate_only', 'sources'} or value.get('schema') != COMPOSITION or value.get('game') != 'wuwa' or (value.get('candidate_only') is not True) or (not isinstance(value.get('sources'), list)) or (not 2 <= len(value['sources']) <= 3):
        raise ValueError('Explicit bounded historical navigation composition required')
    result, origins, seen = (None, [], set())
    for binding in value['sources']:
        file, source = reference(path, binding, dependencies)
        if file in seen:
            raise ValueError('Duplicate historical navigation source')
        seen.add(file)
        if source.get('schema') != 'native-inventory-navigation/v1' or source.get('game') != 'wuwa' or source.get('ready') is not True or (source.get('candidate_only') is not True) or (not isinstance(source.get('native_evidence'), str)) or (not source['native_evidence']) or (not isinstance(source.get('tabs'), dict)) or (not source['tabs']):
            raise ValueError('Composition cannot recursively inherit or invent a route')
        resources(source.get('resource_fingerprints'))
        if result is None:
            result = deepcopy(source)
        else:
            if result.get('game_exe_sha256') != source.get('game_exe_sha256'):
                raise ValueError('Historical navigation binaries conflict')
            for field in ('resource_fingerprints', 'tabs'):
                for key, item in source[field].items():
                    if key in result[field] and result[field][key] != item:
                        raise ValueError('Historical navigation bindings conflict')
                    result[field][key] = deepcopy(item)
        origins.append({'file': file.name, 'sha256': binding['sha256'], 'game_version': source.get('game_version'), 'resource_fingerprints': deepcopy(source['resource_fingerprints']), 'native_evidence': source['native_evidence']})
    result['native_evidence'] = 'COMPOSED OLD ROUTES ONLY: ' + '; '.join((r['native_evidence'] for r in origins))
    result['recognition_basis'] = {'kind': 'pinned_historical_route_composition', 'sources': origins, 'combined_native_acceptance': 'unproven_before_capture'}
    result['automatic_navigation_verified'] = result['combined_native_verified'] = False
    return result

def reference(path, binding, dependencies):
    if not isinstance(binding, dict) or set(binding) != {'file', 'sha256'} or (not isinstance(binding.get('file'), str)) or (re.fullmatch('[A-Za-z0-9_-]+\\.json', binding['file']) is None) or (not isinstance(binding.get('sha256'), str)) or (re.fullmatch('[a-f0-9]{64}', binding['sha256']) is None):
        raise ValueError('Exact sibling version-trial reference required')
    lexical = path.parent / binding['file']
    file = lexical.resolve(strict=True)
    if file != lexical or file == path or file.stat().st_size > 1024 * 1024:
        raise ValueError('Version-trial reference escapes bounded sibling scope')
    raw = file.read_bytes()
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('Version-trial input changed; re-review required')
    value = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Version-trial object required')
    dependencies[str(file)] = binding['sha256']
    return (file, value)

def resources(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 256:
        raise ValueError('Bounded resource catalog required')
    for name, digest in value.items():
        if not isinstance(name, str) or not name or '\\' in name or (':' in name) or PurePosixPath(name).is_absolute() or ('..' in PurePosixPath(name).parts) or (not isinstance(digest, str)) or (re.fullmatch('[a-f0-9]{64}', digest) is None):
            raise ValueError('Invalid version-trial resource fingerprint')

def resolve(path, value, game, kind, load_calibration):
    path = Path(path).resolve(strict=True)
    if game != 'wuwa' or kind not in ('calibration', 'navigation') or set(value) != {'schema', 'game', 'ready', 'candidate_only', 'kind', 'base', 'version'} or (value.get('schema') != SCHEMA) or (value.get('game') != game) or (value.get('ready') is not True) or (value.get('candidate_only') is not True) or (value.get('kind') != kind):
        raise ValueError('Explicit WuWa candidate version trial required')
    dependencies = {}
    base_path, base = reference(path, value['base'], dependencies)
    _, review = reference(path, value['version'], dependencies)
    if set(review) != {'schema', 'game', 'candidate_only', 'game_version', 'game_exe_sha256', 'resource_fingerprints', 'ui_compatibility'} or review.get('schema') != 'inventory-resource-read-trial/v1' or review.get('game') != game or (review.get('candidate_only') is not True) or (review.get('ui_compatibility') != 'unproven_before_capture') or (not isinstance(review.get('game_version'), str)) or (not review['game_version'].strip()) or (not isinstance(review.get('game_exe_sha256'), str)) or (re.fullmatch('[a-f0-9]{64}', review['game_exe_sha256']) is None):
        raise ValueError('Resource review cannot claim native UI acceptance')
    resources(review.get('resource_fingerprints'))
    allowed = ('native-bag-calibration/v1', 'native-bag-layout-selection/v1')
    if kind == 'calibration':
        if base.get('schema') not in allowed:
            raise ValueError('Recursive version inheritance forbidden')
        base = load_calibration(base_path, game)
        tab = base['page_anchor']['text']
        if 'stock_anchor' in base:
            raise ValueError('Unmeasured reward-popup version inheritance forbidden')
        if tab == '资源':
            valid = all((RESOURCE_ITEMS.get(row['id']) == (row['name'], row['category']) for row in base['materials']))
        elif tab == '武器':
            names = {'basic': '初级', 'medium': '中级', 'advanced': '高级', 'premium': '特级'}
            valid = all((any((row['id'] == f'weapon-exp-{q}' and row['name'] == n + '能源核心' and (row['category'] == 'weapon_exp') for q, n in names.items())) for row in base['materials']))
        elif tab == '贝币':
            valid = len(base['materials']) == 1 and (base['materials'][0]['id'], base['materials'][0]['name'], base['materials'][0]['category']) == ('shell-credit', '贝币', 'currency') and (base['materials'][0]['label_roi'] == base['page_anchor']['roi'])
        elif tab == '素材':
            valid = len(base['materials']) == 1 and (base['materials'][0]['id'], base['materials'][0]['name'], base['materials'][0]['category']) == ('promotion-denglongguo', '灯笼果', 'character_promotion')
        else:
            valid = False
        if not valid:
            raise ValueError('Version trial requires exact measured cultivation identities and tab')
        dependencies.update(base.get('_dependency_sha256', {}))
    else:
        if base.get('schema') == COMPOSITION:
            base = compose_navigation(base_path, base, dependencies)
        if base.get('schema') != 'native-inventory-navigation/v1' or base.get('game') != game or base.get('ready') is not True or (base.get('candidate_only') is not True) or (not isinstance(base.get('native_evidence'), str)) or (not base['native_evidence']) or (not {'资源', '武器'}.issubset(base.get('tabs', {}))) or set(base.get('tabs', {})) - {'资源', '武器', '贝币', '素材'} or any((not isinstance(tab, dict) or tab.get('strategy', 'grid') != ('readonly_currency_popup' if name == '贝币' else 'grid') for name, tab in base['tabs'].items())):
            raise ValueError('Only measured cultivation grids and ordinary currency route may be inherited')
    resources(base.get('resource_fingerprints'))
    old, new = (base['resource_fingerprints'], review['resource_fingerprints'])
    if base.get('game_exe_sha256') != review['game_exe_sha256'] or len(new) <= len(old) or any((new.get(name) != digest for name, digest in old.items())):
        raise ValueError('Version trial requires unchanged binary and additive unchanged resources')
    result = {key: deepcopy(item) for key, item in base.items() if not key.startswith('_')}
    result.update(candidate_only=True, game_version=review['game_version'], resource_fingerprints=deepcopy(new))
    result['native_evidence'] = 'OLD LAYOUT ONLY; CURRENT UI UNPROVEN: ' + base['native_evidence']
    result['recognition_basis'] = {'kind': 'additive_hot_update_layout_read_trial', 'base_sha256': value['base']['sha256'], 'version_review_sha256': value['version']['sha256'], 'source_game_version': base.get('game_version'), 'source_resource_fingerprints': deepcopy(old), 'source_recognition_basis': deepcopy(base.get('recognition_basis')), 'ui_compatibility': 'unproven_before_capture', 'per_item_native_acceptance': 'unproven_before_capture'}
    if kind == 'navigation':
        result['automatic_navigation_verified'] = False
        result['combined_native_verified'] = False
    raw = path.read_bytes()
    if len(raw) > 1024 * 1024 or json.loads(raw.decode('utf-8-sig')) != value:
        raise ValueError('Version recipe changed during resolution')
    for name, digest in dependencies.items():
        file = Path(name)
        if file.stat().st_size > 1024 * 1024 or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError('Version-trial dependency changed during resolution')
    result['_source_file_sha256'] = hashlib.sha256(raw).hexdigest()
    dependencies[str(path)] = result['_source_file_sha256']
    result['_dependency_sha256'] = dependencies
    return result
