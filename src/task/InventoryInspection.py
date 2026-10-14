from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Opt-in inventory callable; navigation stays gated by native calibration.

Never changes daily settings, opens a game, runs login, or farms materials.
"""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import time
DEFAULT_ROOT = inventory_root()

def load_module(name, file):
    return import_support(file)
_config = load_module('okww_inventory_task_config', DEFAULT_ROOT / 'tools/inventory-task-config.py')
config_path = _config.config_path
NativeVersions = _config.NativeVersions

def prepare(root, bridge, navigation, selected_ids=None):
    return _config.prepare(root, bridge, navigation, 'wuwa', selected_ids=selected_ids)

def scan_details(navigation, mode, *args, **kwargs):
    """Dispatch the preflighted plan without silently reverting to per-item scans."""
    if mode == 'grouped':
        return navigation.scan_grouped_details(*args, **kwargs)
    if mode == 'single_pass':
        return navigation.scan_selected_details(*args, **kwargs)
    raise ValueError('Batch callback requires an explicit batch scan mode')

def run_inventory_inspection(task, root=DEFAULT_ROOT, *, prepare_gameplay=None, selected_ids=None):
    """Log even a pending/invalid configuration; never fall back to old reports."""
    root = Path(root).resolve(strict=True)
    folder = root / 'audits' / datetime.now().strftime('%Y-%m-%d') / 'inventory' / datetime.now().strftime('okww-dispatch-%H%M%S-%f')
    folder.mkdir(parents=True, exist_ok=False)
    attempt = {'schema': 'inventory-task-dispatch/v1', 'game': 'wuwa', 'phase': 'preflight', 'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'started', 'scope': 'inspection_only', 'task_id': 'InventoryInspectionTask', 'implementation_file': str(Path(__file__).resolve()), 'native_input_may_have_occurred': False, 'farming_changed': False}
    try:
        result = _run_inventory_inspection(task, root, attempt, prepare_gameplay=prepare_gameplay, selected_ids=selected_ids)
        attempt.update(status='selected_inspection_finished', phase='finished', confirmed=sum((row['status'] == 'confirmed' for row in result['materials'])))
        return result
    except Exception as exc:
        attempt.update(status='failed_or_pending_no_success_report', error_type=type(exc).__name__, error=str(exc)[:2000])
        raise
    finally:
        attempt['finished_at'] = datetime.now(timezone.utc).isoformat()
        file = folder / 'attempt.json'
        staged = file.with_suffix('.json.tmp')
        try:
            staged.write_text(json.dumps(attempt, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            os.replace(staged, file)
        finally:
            staged.unlink(missing_ok=True)

def _run_inventory_inspection(task, root, attempt, *, prepare_gameplay=None, selected_ids=None):
    root = Path(root).resolve(strict=True)
    bridge = load_module('okww_inventory_bridge', root / 'tools/inventory-task-session.py')
    navigation = load_module('okww_inventory_navigation', root / 'tools/inventory-native-navigation.py')
    plan, selections, manifest = prepare(root, bridge, navigation) if selected_ids is None else prepare(root, bridge, navigation, selected_ids)
    attempt['phase'] = 'native_process_and_versions'
    from src.task.InventoryBagPort import NativeBagPort
    import psutil
    import win32gui
    import win32process


    def identity():
        window = task.hwnd
        handle = getattr(window, 'hwnd', 0)
        if not handle or not win32gui.IsWindow(handle) or win32gui.IsIconic(handle):
            raise RuntimeError('当前助手没有可交互的鸣潮窗口')
        pid = win32process.GetWindowThreadProcessId(handle)[1]
        process = psutil.Process(pid)
        return {'pid': pid, 'path': process.exe(), 'created': datetime.fromtimestamp(process.create_time(), timezone.utc).isoformat()}
    expected = identity()
    executable = expected['path']
    if not valid_game_path('wuwa', executable):
        raise RuntimeError('原生窗口不是目标游戏')
    if not bridge.same_identity(expected, dict(expected, path=executable)):
        raise RuntimeError('当前助手窗口不是已配置的鸣潮安装')
    versions = NativeVersions(bridge.probe, executable)
    expected_versions = {'game_exe_sha256': manifest['game_exe_sha256'], 'resource_fingerprints': manifest['resource_fingerprints']}
    deadline = time.monotonic() + plan['budget_seconds']

    def lane_available():
        return getattr(task.executor, 'current_task', None) is task and (not getattr(task.executor, 'paused', False))

    def cancelled():
        return not getattr(task, '_enabled', False) or getattr(task.executor, 'paused', False)

    def control_guard():
        task.executor.check_enabled()
        if cancelled() or not lane_available():
            raise RuntimeError('仓库检查已取消、暂停或执行权改变')
        if time.monotonic() >= deadline:
            raise TimeoutError('仓库检查总预算已用尽')

    def guard():
        control_guard()
        bridge.probe.check_calibration_sources(manifest)
        if not bridge.same_identity(expected, identity()) or versions() != expected_versions:
            raise RuntimeError('鸣潮窗口身份或游戏资源版本改变，停止操作')
        bridge.probe.check_calibration_sources(manifest)
        control_guard()
    guard()
    if prepare_gameplay is not None:
        attempt.update(phase='waiting_for_gameplay', native_input_may_have_occurred=True)
        prepare_gameplay()
        guard()
    port = NativeBagPort(task, guard)
    events = []

    def event(name, details):
        events.append({'at': datetime.now(timezone.utc).isoformat(), 'event': name, **details})
    selected_iter = iter(selections)

    def navigate(path, cfg):
        guard()
        expected_path, material_id = next(selected_iter)
        if path != expected_path:
            raise RuntimeError('Selected page order changed')
        return navigation.find_selected_detail(port, cfg, manifest, guard, material_id=material_id, budget_seconds=min(60, max(1, int(deadline - time.monotonic()))), event=event)

    def batch_scan(pages, capture):
        guard()
        if [path for path, _ in pages] != [path for path, _ in selections]:
            raise RuntimeError('Batch page order changed')
        return scan_details(navigation, plan['scan_mode'], port, [(cfg, item_id) for (_, cfg), (_, item_id) in zip(pages, selections)], manifest, guard, capture, budget_seconds=max(1, int(deadline - time.monotonic())), event=event)
    folder = root / 'audits' / datetime.now().strftime('%Y-%m-%d') / 'inventory' / datetime.now().strftime('okww-task-%H%M%S-%f')
    attempt['session_audit'] = str(folder)
    try:
        attempt.update(phase='native_navigation_and_capture', native_input_may_have_occurred=True)
        result = bridge.inspect_session('wuwa', [file for file, _ in selections], expected, navigate=navigate, current_identity=identity, current_versions=versions, lane_available=lane_available, cancelled=cancelled, audit_folder=folder, budget_seconds=plan['budget_seconds'], deadline_at=deadline, collector=lambda game, identity, path, seconds: collect_native_page(port, game, identity, path, seconds, probe=bridge.probe, folder=folder / datetime.now().strftime('capture-%H%M%S-%f'), guard=guard), batch_scan=batch_scan if plan.get('scan_mode') in ('single_pass', 'grouped') else None)
        count = sum((row['status'] == 'confirmed' for row in result['materials']))
        task.info_set('库存检查', f'已核实{count}项；仅选定材料，不代表全仓库')
        task.log_info(f"inventory inspection report: {folder / 'report.json'}")
        return result
    finally:
        if folder.is_dir():
            bridge.probe.atomic_json(folder / 'navigation-events.json', events)
            bridge.probe.atomic_json(folder / 'native-port-metrics.json', port.diagnostics())
