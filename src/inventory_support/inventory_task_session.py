from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
def collect_page(*args):
    raise RuntimeError('必须由当前助手提供库存读取接口')
"Opt-in inventory task bridge; native navigation remains an injected adapter.\n\nThis is NOT a production task registration. A caller must own an idle assistant\nlane, supply calibrated read-only bag navigation, and keep the same game process.\nOCR runs in the existing collector's separate process: its chdir/model lifecycle\nmust not mutate an assistant's global working directory or OCR instance.\n"
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
import subprocess
import time
ROOT = inventory_root()

def load_module(name, path):
    return import_support(path)
probe = load_module('inventory_session_probe', ROOT / 'tools/inventory-native-probe.py')
observation = probe.observation

def same_identity(expected, actual):
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    try:
        return type(expected['pid']) is int and expected['pid'] > 0 and (type(actual['pid']) is int) and (expected['pid'] == actual['pid']) and (abs((observation.timestamp(expected['created']) - observation.timestamp(actual['created'])).total_seconds()) <= 0.01) and isinstance(expected['path'], str) and isinstance(actual['path'], str) and bool(expected['path']) and bool(actual['path']) and (os.path.normcase(os.path.normpath(expected['path'])) == os.path.normcase(os.path.normpath(actual['path'])))
    except (KeyError, ValueError, TypeError, OverflowError):
        return False

def validate_pages(game, paths):
    if game not in probe.SPECS or not isinstance(paths, list) or (not 1 <= len(paths) <= 128):
        raise ValueError('Expected one supported game and 1..128 calibrated pages')
    result = []
    for path in paths:
        path = Path(path).resolve(strict=True)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('Calibration too large')
        cfg = probe.load_calibration(path, game)
        result.append((path, cfg))
    first = result[0][1]
    if any((cfg['game_exe_sha256'].lower() != first['game_exe_sha256'].lower() or cfg['resource_fingerprints'] != first['resource_fingerprints'] for _, cfg in result)):
        raise ValueError('Mixed native page versions')
    identities = {}
    for _, cfg in result:
        for row in cfg['materials']:
            signature = (row['name'], row['category'], row.get('target'))
            if row['id'] in identities and identities[row['id']] != signature:
                raise ValueError('Cross-page material name, quality, category or target changed')
            identities[row['id']] = signature
    return result

def incomplete_report(game, pages, reports, *, stopped_phase, error_type, error, now=None):
    """Diagnostic snapshot only, never current inventory or task success.

    Keep original capture times and sources. Do not read the game again after
    cancellation/version loss. Earlier counts remain historical observations;
    unread targets are unknown, not zero. Never pass this schema to a planner.
    """
    now = now or datetime.now(timezone.utc)
    expected = {}
    for _, cfg in pages:
        for material in cfg['materials']:
            expected.setdefault(material['id'], material)
    previous, source_issue = ({}, None)
    if reports:
        try:
            merged = observation.merge_reports(game, reports, now=now)
            previous = {row['id']: row for row in merged['materials']}
        except (ValueError, TypeError, KeyError) as exc:
            source_issue = str(exc)[:500]
    rows = []
    for item_id, material in expected.items():
        old = previous.get(item_id)
        row = {'id': item_id, 'name': material['name'], 'category': material['category'], 'status': 'unverified', 'quantity': None, 'shortage': None, 'reason': 'inspection_stopped_no_current_quantity'}
        if material.get('target') is not None:
            row['target'] = material['target']
        if old:
            row['earlier_observation'] = old
        rows.append(row)
    return {'schema': 'inventory-incomplete-report/v1', 'game': game, 'reported_at': now.isoformat(), 'status': 'incomplete_inspection', 'current_inventory_verified': False, 'complete_inventory': False, 'scope': 'inspection_diagnostics_only', 'farming_changed': False, 'stopped_phase': stopped_phase, 'error_type': error_type, 'error': error[:2000], 'completed_pages': len(reports), 'planned_pages': len(pages), 'source_validation_issue': source_issue, 'materials': rows, 'note': 'Earlier observations keep their capture times; they do not prove current stock or completion.'}

def inspect_session(game, calibration_paths, identity, *, navigate, current_identity, current_versions, lane_available, cancelled, audit_folder, budget_seconds=300, collector=collect_page, clock=time.monotonic, deadline_at=None, batch_scan=None, selected_material_ids=None):
    """Read-only inspection transaction for future native assistant adapters.

    navigate(path, cfg) must use the caller's native, read-only bag navigation,
    without starting a game, opening destructive item handling, or purchasing.
    It returns True only after reaching that selected detail. All other injected
    callbacks are required; this function cannot infer lane ownership or input.
    The caller must bound navigation itself and honor pause/stop inside it.
    Optional batch_scan(pages, capture_index) traverses a calibrated grid once;
    capture_index must be called immediately at the corresponding selected
    detail. All configured indices must be captured, exactly once. Missing
    selections produce incomplete-report.json, never zero stock or success.
    """
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 600:
        raise ValueError('Session budget must be 1..600 seconds')
    if deadline_at is not None and (isinstance(deadline_at, bool) or not isinstance(deadline_at, (int, float)) or (not isfinite(deadline_at)) or (deadline_at < 0)):
        raise ValueError('Expected finite monotonic parent deadline')
    folder = Path(audit_folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    attempt = {'schema': 'inventory-task-attempt/v1', 'game': game, 'status': 'started', 'started_at': datetime.now(timezone.utc).isoformat(), 'phase': 'preflight', 'completed_pages': 0, 'scope': 'inspection_only', 'farming_changed': False, 'navigation_is_native_verified': False}
    started_clock = clock()
    deadline = started_clock + budget_seconds
    if deadline_at is not None:
        deadline = min(deadline, deadline_at)
    attempt['budget_seconds'] = budget_seconds
    attempt['remaining_budget_seconds_at_start'] = max(0, deadline - started_clock)
    reports, expected_versions, calibration_hashes = ([], None, {})
    target_path = ROOT / 'config/inventory-stock-targets.json'
    target_hash, targets = (None, {})
    required_path = ROOT / 'config/cultivation-required-materials.json'
    required_hash, required_catalog = (None, None)
    pages = []

    def control_guard():
        if cancelled():
            raise RuntimeError('Inspection cancelled; no further input')
        if clock() >= deadline:
            raise TimeoutError('Inspection budget exhausted')
        if lane_available() is not True:
            raise RuntimeError('Assistant lane unavailable; no further input')

    def guard():
        control_guard()
        if target_hash is not None and (not target_path.is_file() or probe.file_sha256(target_path) != target_hash):
            raise RuntimeError('Stock targets changed during inspection; no further input')
        if required_hash is not None and (not required_path.is_file() or probe.file_sha256(required_path) != required_hash):
            raise RuntimeError('Cultivation catalog changed during inspection; no further input')
        if not same_identity(identity, current_identity()):
            raise RuntimeError('Game process identity changed; no further input')
        if current_versions() != expected_versions:
            raise RuntimeError('Game binary or hot-update version changed; no further input')
        for path, digest in calibration_hashes.items():
            if path.stat().st_size > 1024 * 1024 or probe.file_sha256(path) != digest:
                raise RuntimeError('Inventory calibration/target changed during execution; no further input')
        control_guard()
    try:
        target_hash = probe.file_sha256(target_path) if target_path.is_file() else None
        if target_hash is not None:
            if target_path.stat().st_size > 1024 * 1024:
                raise ValueError('Stock target configuration too large; no input')
            targets = observation.stock_targets(json.loads(target_path.read_text(encoding='utf-8-sig')), game)
        required_hash = probe.file_sha256(required_path) if required_path.is_file() else None
        if required_hash is not None:
            if required_path.stat().st_size > 1024 * 1024:
                raise ValueError('Cultivation catalog too large; no input')
            candidate_catalog = json.loads(required_path.read_text(encoding='utf-8-sig'))
            observation.required_materials(candidate_catalog, game)
            required_catalog = candidate_catalog
        attempt['configuration_snapshots'] = {'stock_targets_sha256': target_hash, 'required_catalog_sha256': required_hash}
        pages = validate_pages(game, calibration_paths)
        calibration_hashes = {path: cfg['_source_file_sha256'] for path, cfg in pages}
        for _, cfg in pages:
            for name, digest in cfg.get('_dependency_sha256', {}).items():
                path = Path(name)
                if path in calibration_hashes and calibration_hashes[path] != digest:
                    raise ValueError('Conflicting inherited input identity; no input')
                calibration_hashes[path] = digest
        attempt['calibration_hashes'] = {str(path): digest for path, digest in calibration_hashes.items()}
        expected_versions = {'game_exe_sha256': pages[0][1]['game_exe_sha256'].lower(), 'resource_fingerprints': pages[0][1]['resource_fingerprints']}
        if not valid_game_path(game, identity.get('path')):
            raise ValueError('Game identity is not the configured installation')
        captured_indices = []

        def capture_selected(index):
            if type(index) is not int or not 0 <= index < len(pages) or index in captured_indices:
                raise ValueError('Invalid or duplicate batch capture index')
            path, cfg = pages[index]
            guard()
            attempt.update(phase='passive_capture', page=index, calibration=str(path))
            probe.atomic_json(folder / 'attempt.json', attempt)
            remaining = min(90, int(deadline - clock()))
            if remaining < 1:
                raise TimeoutError('No remaining capture budget')
            if selected_material_ids is not None:
                if len(selected_material_ids) != len(pages):
                    raise ValueError('已选材料与识别页面不匹配')
                page = collector(game, identity, path, remaining, selected_ids=[selected_material_ids[index]])
            else:
                page = collector(game, identity, path, remaining)
            guard()
            if not same_identity(identity, page.get('game_identity')) or page.get('game_exe_sha256') != expected_versions['game_exe_sha256'] or page.get('resource_fingerprints') != expected_versions['resource_fingerprints']:
                raise RuntimeError('Capture does not match guarded process/version')
            observation.merge_reports(game, reports + [page])
            reports.append(page)
            captured_indices.append(index)
            probe.atomic_json(folder / 'source-reports.json', reports)
            attempt['completed_pages'] = len(reports)
        if batch_scan is not None:
            if not callable(batch_scan):
                raise ValueError('Native batch scanner must be callable')
            guard()
            attempt.update(phase='native_batch_navigation', traversal='single_pass')
            probe.atomic_json(folder / 'attempt.json', attempt)
            scanned = batch_scan(pages, capture_selected)
            guard()
            if not isinstance(scanned, list) or any((type(index) is not int for index in scanned)) or scanned != captured_indices or (set(scanned) != set(range(len(pages)))):
                raise RuntimeError('Native batch selection incomplete; unread stock unknown')
        else:
            for index, (path, cfg) in enumerate(pages):
                guard()
                attempt.update(phase='native_navigation', page=index, calibration=str(path))
                probe.atomic_json(folder / 'attempt.json', attempt)
                if navigate(path, cfg) is not True:
                    raise RuntimeError('Native selected material detail not reached')
                guard()
                capture_selected(index)
        result = observation.merge_reports(game, reports)
        if targets:
            result = observation.apply_stock_targets(result, targets)
        if required_catalog is not None:
            result = observation.apply_required_materials(result, required_catalog)
        result['native_navigation_adapter'] = 'caller_supplied_not_validated_by_this_bridge'
        result['production_task_registered'] = False
        guard()
        probe.atomic_json(folder / 'report.json', result)
        attempt.update(status='finished_selected_pages', phase='report_saved', confirmed=sum((r['status'] == 'confirmed' for r in result['materials'])))
        return result
    except Exception as exc:
        attempt.update(status='failed_no_session_report', error_type=type(exc).__name__, error=str(exc)[:2000])
        partial = incomplete_report(game, pages, reports, stopped_phase=attempt['phase'], error_type=type(exc).__name__, error=str(exc))
        partial['configuration_snapshots'] = {'stock_targets_sha256': target_hash, 'required_catalog_sha256': required_hash}
        for label, annotate in (('stock_targets', lambda report: observation.apply_stock_targets(report, targets)), ('required_catalog', lambda report: observation.apply_required_materials(report, required_catalog))):
            if label == 'stock_targets' and (not targets) or (label == 'required_catalog' and required_catalog is None):
                continue
            try:
                partial = annotate(partial)
            except (ValueError, KeyError, TypeError) as diagnostic_error:
                partial.setdefault('diagnostic_annotation_errors', {})[label] = str(diagnostic_error)[:500]
        probe.atomic_json(folder / 'incomplete-report.json', partial)
        attempt['incomplete_report'] = str(folder / 'incomplete-report.json')
        raise
    finally:
        attempt['finished_at'] = datetime.now(timezone.utc).isoformat()
        probe.atomic_json(folder / 'attempt.json', attempt)
