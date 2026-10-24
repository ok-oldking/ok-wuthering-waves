from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Conservative inventory report layer. No game input and no farming decisions.

Native bag adapters must supply a bound label/count crop and capture timestamp;
this layer never pairs arbitrary adjacent OCR strings or infers missing = zero.
"""
from datetime import datetime, timezone
from decimal import Decimal
import re
import unicodedata
from copy import deepcopy
CATEGORIES = ('currency', 'character_exp', 'character_promotion', 'weapon_exp', 'weapon_promotion', 'skill', 'core_skill_expert', 'weekly_boss')

def required_materials(value, game):
    """Sourced identities only; this catalog is never a native scan or target."""
    if not isinstance(value, dict) or value.get('schema') != 'cultivation-required-materials/v1' or game not in ('wuwa', 'zzz') or (type(value.get('complete_catalog')) is not bool) or (not isinstance(value.get('sources'), dict)):
        raise ValueError('Invalid cultivation catalog')
    rows = value.get('materials')
    if not isinstance(rows, list) or len(rows) > 4096:
        raise ValueError('Expected bounded required materials')
    seen, result = (set(), {})
    for row in rows:
        if not isinstance(row, dict) or row.get('game') not in ('wuwa', 'zzz') or (not all((isinstance(row.get(k), str) and row[k].strip() for k in ('id', 'name', 'category', 'quality', 'source')))) or (row['category'] not in CATEGORIES) or (not isinstance(value['sources'].get(row['source']), str)) or (not value['sources'][row['source']].strip()):
            raise ValueError('Exact sourced required material identity needed')
        key = (row['game'], row['id'])
        if key in seen:
            raise ValueError('Duplicate required material')
        seen.add(key)
        if row['game'] == game:
            result[row['id']] = deepcopy(row)
    return result

def apply_required_materials(value, catalog):
    """Expose gaps in this session without inserting fake native rows/counts."""
    required = required_materials(catalog, value['game'])
    result = deepcopy(value)
    seen = set()
    confirmed = 0
    for row in result['materials']:
        item = required.get(row['id'])
        if item is None:
            continue
        if (row['name'], row['category']) != (item['name'], item['category']):
            raise ValueError('Required material conflicts with native identity')
        seen.add(row['id'])
        if row.get('status') == 'confirmed' and type(row.get('quantity')) is int:
            confirmed += 1
    result['required_materials_without_observation'] = [dict(item, status='unverified', quantity=None, shortage=None, reasons=['not_observed_in_this_selected_scan']) for item_id, item in required.items() if item_id not in seen]
    result['cultivation_coverage_summary'] = {'catalog_complete': catalog['complete_catalog'], 'catalog_items_for_game': len(required), 'confirmed_catalog_items': confirmed, 'unobserved_catalog_items': len(required) - len(seen), 'observed_but_unverified_catalog_items': len(seen) - confirmed, 'full_cultivation_inventory_verified': False, 'note': 'A partial catalog is not the full denominator; unread stock is unknown, not zero.'}
    return result

def catalog_display_rows(catalog, game, targets):
    """Read-only UI denominator; missing targets stay unset, never default20.

    Neither membership nor a historical quantity authorizes a scan or battle.
    The catalog remains partial even when all its listed items are displayed.
    """
    required = required_materials(catalog, game)
    configured = stock_targets({'schema': 'inventory-stock-targets/v1', 'games': {game: targets}}, game)
    rows = []
    for item_id, row in configured.items():
        item = required.get(item_id)
        if item is not None and (row['name'], row['category']) != (item['name'], item['category']):
            raise ValueError('Display target conflicts with sourced identity')
        rows.append(dict(row, quantity=None, observed_at=None))
    rows.extend((dict(item, target=None, quantity=None, observed_at=None) for item_id, item in required.items() if item_id not in configured))
    return rows

def stock_targets(value, game):
    """Editable explicit thresholds, not a cultivation cost or farming plan."""
    if not isinstance(value, dict) or value.get('schema') != 'inventory-stock-targets/v1' or game not in ('wuwa', 'zzz') or (not isinstance(value.get('games'), dict)):
        raise ValueError('Invalid inventory stock target configuration')
    rows = value['games'].get(game, [])
    if not isinstance(rows, list) or len(rows) > 256:
        raise ValueError('Expected bounded stock target list')
    result = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id', 'name', 'category', 'target'} or (not isinstance(row['id'], str)) or (not row['id']) or (row['id'] in result) or (not isinstance(row['name'], str)) or (not row['name']) or (row['category'] not in CATEGORIES) or (type(row['target']) is not int) or (not 1 <= row['target'] <= 10 ** 9):
            raise ValueError('Exact material identity and positive target required')
        result[row['id']] = deepcopy(row)
    return result

def apply_stock_targets(value, targets):
    """Annotate this scan only; unobserved targets stay separate and unknown."""
    result = deepcopy(value)
    seen = set()
    for row in result['materials']:
        target = targets.get(row['id'])
        if target is None:
            continue
        if (row['name'], row['category']) != (target['name'], target['category']):
            raise ValueError('Stock target label/quality/category does not match native identity')
        seen.add(row['id'])
        count = row.get('quantity')
        confirmed = row.get('status') == 'confirmed' and type(count) is int and (count >= 0)
        row['target'] = target['target']
        row['shortage'] = max(0, target['target'] - count) if confirmed else None
    result['targets_without_observation'] = [dict(target, status='unverified', quantity=None, shortage=None, reasons=['not_observed_in_this_selected_scan']) for item_id, target in targets.items() if item_id not in seen]
    result['stock_target_summary'] = {'configured': len(targets), 'evaluated': sum((row['id'] in seen and row.get('shortage') is not None for row in result['materials'])), 'unobserved': len(result['targets_without_observation']), 'automatically_farm': False, 'scope': 'user_editable_stock_cushion_not_universal_cultivation_bill'}
    return result

def quantity(text):
    """Return an exact integer, or a display estimate that cannot pass a target."""
    text = unicodedata.normalize('NFKC', str(text)).strip()
    text = re.sub('^[x×]\\s*', '', text, flags=re.I)
    if re.fullmatch('(?:0|[1-9]\\d*|[1-9]\\d{0,2}(?:,\\d{3})+)', text):
        number = int(text.replace(',', ''))
        if number <= 2 ** 63 - 1:
            return {'status': 'exact', 'quantity': number}
    match = re.fullmatch('(\\d+(?:\\.\\d+)?)(万|亿|[kKmM])', text)
    if match:
        scale = {'万': 10000, '亿': 100000000, 'k': 1000, 'm': 1000000}[match[2].lower()]
        return {'status': 'approximate', 'quantity': None, 'display_estimate': str(Decimal(match[1]) * scale)}
    return {'status': 'unknown', 'quantity': None}

def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Capture timestamp requires timezone')
    return parsed

def report(game, materials, frames, now=None, max_age_seconds=3600):
    if game not in ('zzz', 'wuwa'):
        raise ValueError('Unsupported inventory game')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Report timestamp requires timezone')
    rows = []
    for material in materials:
        item_id = material['id']
        candidates = []
        rejected = []
        for frame in frames:
            if frame.get('game') != game or frame.get('source') != 'native-bag-ocr':
                continue
            for observed in frame.get('items', []):
                if observed.get('id') != item_id:
                    continue
                try:
                    if frame.get('page_verified') is not True:
                        raise ValueError('native_page_not_verified')
                    when = timestamp(frame['captured_at'])
                    age = (now - when).total_seconds()
                    if not -5 <= age <= max_age_seconds:
                        raise ValueError('stale_capture')
                    if not frame.get('frame_id') or not frame.get('evidence'):
                        raise ValueError('missing_evidence')
                    if observed.get('bound_label') != material['name']:
                        raise ValueError('label_not_bound')
                    for key in ('label_roi', 'quantity_roi'):
                        roi = observed.get(key)
                        if not isinstance(roi, list) or len(roi) != 4 or (not all((isinstance(n, int) and (not isinstance(n, bool)) and (n >= 0) for n in roi))) or (roi[2] == 0) or (roi[3] == 0):
                            raise ValueError('missing_bound_roi')
                    for key in ('label_confidence', 'quantity_confidence'):
                        score = observed.get(key, -1)
                        if isinstance(score, bool) or not isinstance(score, (int, float)) or (not 0.9 <= score <= 1):
                            raise ValueError('low_confidence')
                    parsed = quantity(observed.get('quantity_text', ''))
                    if parsed['status'] != 'exact':
                        raise ValueError(parsed['status'] + '_quantity')
                    candidates.append((frame['frame_id'], parsed['quantity'], when.isoformat(), frame['evidence'], observed.get('crop_evidence', []), observed['label_confidence'], observed['quantity_confidence']))
                except (ValueError, TypeError, KeyError) as exc:
                    rejected.append(str(exc))
        unique = {entry[0]: entry for entry in candidates}
        counts = {entry[1] for entry in candidates}
        capture_times = {entry[2] for entry in unique.values()}
        confirmed = len(unique) >= 2 and len(capture_times) >= 2 and (len(counts) == 1) and (not rejected)
        row = {'id': item_id, 'name': material['name'], 'category': material['category'], 'status': 'confirmed' if confirmed else 'unverified', 'quantity': next(iter(counts)) if confirmed else None, 'confidence': min((min(x[5], x[6]) for x in unique.values())) if confirmed else None, 'evidence': [{'frame_id': x[0], 'captured_at': x[2], 'source': x[3], 'crops': x[4], 'label_confidence': x[5], 'quantity_confidence': x[6]} for x in unique.values()], 'reasons': sorted(set(rejected))}
        if len(counts) > 1:
            row['reasons'].append('conflicting_counts')
        elif len(unique) < 2 or len(capture_times) < 2:
            row['reasons'].append('need_two_independent_observations')
        target = material.get('target')
        if target is not None:
            if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
                raise ValueError('Target must be a positive integer')
            row['target'] = target
            row['shortage'] = max(0, target - row['quantity']) if confirmed else None
        rows.append(row)
    return {'schema': 'inventory-report/v1', 'game': game, 'reported_at': now.isoformat(), 'scope': 'inspection_only', 'farming_changed': False, 'materials': rows}

def merge_reports(game, reports, now=None, max_age_seconds=3600):
    """Merge selected pages from one game process/version, never a full census.

    Callers must supply validated native reports. Missing detail on another
    selected page is not a contradiction; different *confirmed* quantities are.
    Original capture times remain authoritative, not the new merge timestamp.
    """
    now = now or datetime.now(timezone.utc)
    if game not in ('zzz', 'wuwa') or now.tzinfo is None or (not reports):
        raise ValueError('Game, timezone and source reports required')
    if not isinstance(reports, list) or len(reports) > 128:
        raise ValueError('Expected bounded source reports')
    identity, binary, resources = (None, None, None)
    items = {}
    for source in reports:
        if not isinstance(source, dict) or source.get('schema') != 'inventory-report/v1' or source.get('game') != game or (source.get('scope') != 'inspection_only') or (source.get('farming_changed') is not False) or (source.get('inventory_coverage') != 'selected_materials_only') or (source.get('page_verified_twice') is not True):
            raise ValueError('Source must be a verified partial native report')
        current = source.get('game_identity')
        if not isinstance(current, dict) or type(current.get('pid')) is not int or current['pid'] <= 0 or (not isinstance(current.get('path'), str)) or (not current['path']):
            raise ValueError('Exact process identity required')
        timestamp(current.get('created'))
        digest, catalog = (source.get('game_exe_sha256'), source.get('resource_fingerprints'))
        if not isinstance(digest, str) or re.fullmatch('[a-f0-9]{64}', digest) is None or (not isinstance(catalog, dict)) or (not catalog):
            raise ValueError('Source game version required')
        if identity is None:
            identity, binary, resources = (deepcopy(current), digest, deepcopy(catalog))
        elif identity != current or binary != digest or resources != catalog:
            raise ValueError('Mixed game process or hot-update versions')
        rows = source.get('materials')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
            raise ValueError('Bounded material rows required')
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or (not row['id']) or (row['id'] in seen) or (not isinstance(row.get('name'), str)) or (not row['name']) or (row.get('category') not in CATEGORIES) or (row.get('status') not in ('confirmed', 'unverified')):
                raise ValueError('Invalid/duplicate material row')
            seen.add(row['id'])
            target = row.get('target')
            if target is not None and (type(target) is not int or target <= 0):
                raise ValueError('Target must be a positive integer')
            if 'shortage' in row and target is None:
                raise ValueError('Shortage requires an explicit target')
            group = items.setdefault(row['id'], [])
            if group and any((row.get(k) != group[0].get(k) for k in ('name', 'category', 'target'))):
                raise ValueError('Material name, quality, category or target changed')
            if row['status'] == 'confirmed':
                if type(row.get('quantity')) is not int or not 0 <= row['quantity'] <= 2 ** 63 - 1 or isinstance(row.get('confidence'), bool) or (not isinstance(row.get('confidence'), (int, float))) or (not 0.9 <= row['confidence'] <= 1):
                    raise ValueError('Exact native count and confidence required')
                evidence = row.get('evidence', [])
                if not isinstance(evidence, list) or not 2 <= len(evidence) <= 128:
                    raise ValueError('Two native capture proofs required')
                frame_ids, times = (set(), set())
                for proof in evidence:
                    when = timestamp(proof['captured_at'])
                    if not -5 <= (now - when).total_seconds() <= max_age_seconds:
                        raise ValueError('Stale source capture')
                    if not isinstance(proof.get('frame_id'), str) or not proof['frame_id']:
                        raise ValueError('Missing source frame identity')
                    frame_ids.add(proof['frame_id'])
                    times.add(when)
                if len(frame_ids) < 2 or len(times) < 2:
                    raise ValueError('Repeated frame is not two observations')
            elif row.get('quantity') is not None:
                raise ValueError('Unverified source must not contain a guessed quantity')
            group.append(deepcopy(row))
    merged = []
    for group in items.values():
        valid = [row for row in group if row['status'] == 'confirmed']
        row = deepcopy(valid[0] if valid else group[0])
        if len({r['quantity'] for r in valid}) > 1:
            row.update(status='unverified', quantity=None, confidence=None, reasons=['conflicting_counts_across_pages'])
            if 'shortage' in row:
                row['shortage'] = None
        elif valid:
            row['confidence'] = min((r['confidence'] for r in valid))
        if row.get('target') is not None:
            row['shortage'] = max(0, row['target'] - row['quantity']) if row['status'] == 'confirmed' else None
        merged.append(row)
    sampled = sorted({r['category'] for r in merged if r['status'] == 'confirmed'})
    return {'schema': 'inventory-session-report/v1', 'game': game, 'reported_at': now.isoformat(), 'scope': 'inspection_only', 'inventory_coverage': 'selected_materials_only', 'complete_inventory': False, 'farming_changed': False, 'game_identity': identity, 'game_exe_sha256': binary, 'resource_fingerprints': resources, 'source_reports': len(reports), 'materials': merged, 'sampled_categories': sampled, 'categories_without_confirmed_samples': sorted(set(CATEGORIES) - set(sampled)), 'coverage_note': 'A sampled category is not a completely scanned category; absence is unknown, not zero.'}
