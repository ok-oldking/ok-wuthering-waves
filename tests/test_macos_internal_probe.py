"""No native window/input calls: verify the opt-in diagnostic and its cleanup."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


spec = importlib.util.spec_from_file_location(
    'macos_internal_probe', Path(__file__).parents[1] / 'scripts/macos_internal_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_read_only_declares_no_input_capabilities():
    required = probe.probe_requirements('read-only')
    assert required.foreground_only
    assert not required.keyboard_tap
    assert not required.keyboard_hold
    assert not required.absolute_mouse


def test_hold_requires_real_hold_provider():
    required = probe.probe_requirements('hold-focus')
    assert required.keyboard_hold and required.foreground_only
    assert not probe.probe_requirements('read-only').supports(required)


def test_unknown_mode_fails_closed():
    with pytest.raises(ValueError):
        probe.probe_requirements('arbitrary-input')


@pytest.mark.parametrize('name, confidence', [('领取奖励', .99), ('紫珊瑚', .8), ('对话', 1)])
def test_autopick_requires_confirmed_fixture(name, confidence):
    with pytest.raises(RuntimeError):
        probe.require_safe_pickup([SimpleNamespace(name=name, confidence=confidence)])


def test_autopick_uses_registered_production_task_composition():
    from src.task.AutoPickTask import AutoPickTask
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._report = {}
    frame = reference_frame(1920, 1080)
    task._executor = SimpleNamespace(frame=frame)
    label = SimpleNamespace(name='紫珊瑚', confidence=.99)
    task.ocr = Mock(side_effect=[[label], [label], []])
    task.next_frame = Mock()
    task.sleep = Mock()
    task.screenshot = Mock()
    task.run_task_by_class = Mock()
    task._probe_autopick_once(frame)
    task.run_task_by_class.assert_called_once_with(AutoPickTask)
    assert task._report['pickup_prompt_before'] is True
    assert task._report['pickup_prompt_after'] is False
    assert probe.probe_requirements('autopick-once').enabled_names() == ('keyboard_tap', 'scroll', 'foreground_only')


def test_guide_requires_only_foreground_absolute_left_click():
    assert probe.probe_requirements('guide-category').enabled_names() == (
        'absolute_mouse', 'mouse_left', 'foreground_only')
    assert probe.probe_requirements('guide-entry').enabled_names() == (
        'absolute_mouse', 'mouse_left', 'foreground_only')


def material_labels():
    return [probe.Box(72, 35, 90, 20, name='素材获取'),
            probe.Box(193, 510, 90, 20, name='无音清剿'),
            probe.Box(193, 590, 90, 20, name='残象聚落')]


def reference_frame(width=1280, height=800, dtype='uint8'):
    return SimpleNamespace(shape=(height, width, 3), dtype=dtype)


@pytest.mark.parametrize('width,height,scale,roi', [
    (1280, 800, 1, (460, 760)), (1920, 1080, 1.5, (690, 1080)),
    (1280, 720, 1, (460, 720)), (1600, 900, 1.25, (575, 900)),
    (1600, 1000, 1.25, (575, 950)), (1920, 1200, 1.5, (690, 1140)),
    (2560, 1440, 2, (920, 1440)), (2560, 1600, 2, (920, 1520)),
])
def test_probe_uses_real_frame_geometry_without_resampling(width, height, scale, roi):
    frame = reference_frame(width, height)
    actual_scale, region = probe.probe_geometry(frame)
    assert actual_scale == scale
    assert (region.width, region.height) == roi
    assert frame.shape == (height, width, 3)
    labels = material_labels()
    for label in labels:
        label.y *= scale
    assert len(probe.require_material_page(labels, scale)) == 3


@pytest.mark.parametrize('frame', [reference_frame(1280, 904), reference_frame(dtype='uint16'),
                                  reference_frame(1024, 640), reference_frame(3440, 1440)])
def test_unapproved_probe_geometry_still_fails_closed(frame):
    with pytest.raises(RuntimeError):
        probe.probe_geometry(frame)


@pytest.mark.parametrize('case', ['missing', 'duplicate', 'wrong-layout'])
def test_guide_precondition_rejects_ambiguous_pages(case):
    labels = material_labels()
    if case == 'missing':
        labels.pop()
    elif case == 'duplicate':
        labels.append(labels[-1])
    else:
        labels[-1].y = 300
    with pytest.raises(RuntimeError):
        probe.require_material_page(labels)


def test_guide_only_calls_installed_category_helper_once(monkeypatch):
    from src.task.BaseWWTask import BaseWWTask
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._report = {'ordinary_attempts': 0}
    frame = reference_frame()
    task._executor = SimpleNamespace(frame=frame)
    task.ocr = Mock(side_effect=[material_labels(), material_labels()])
    task.next_frame = Mock()
    task.find_one = Mock(return_value=None)
    category = Mock()
    monkeypatch.setattr(BaseWWTask, 'open_boss_book', category)
    task._probe_guide_category(frame)
    category.assert_called_once_with(task, 'wuyin', after_sleep=1)
    assert task._report['ordinary_attempts'] == 1
    assert task._report['status'] == 'observed-not-accepted'


def test_guide_wrong_page_never_calls_category(monkeypatch):
    from src.task.BaseWWTask import BaseWWTask
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._report = {'ordinary_attempts': 0}
    task.ocr = Mock(return_value=[])
    category = Mock()
    monkeypatch.setattr(BaseWWTask, 'open_boss_book', category)
    with pytest.raises(RuntimeError):
        task._probe_guide_category(reference_frame())
    category.assert_not_called()
    assert task._report['ordinary_attempts'] == 0


@pytest.mark.parametrize('platform,executable', [
    ('darwin', '/usr/bin/python3'),
    ('darwin', '/tmp/OK-WW Foreground Internal.app/Contents/MacOS/macos_main'),
    ('win32', '/Applications/OK-WW Foreground Internal.app/Contents/MacOS/macos_main'),
])
def test_source_or_other_identity_rejected(platform, executable):
    with pytest.raises(RuntimeError):
        probe.require_installed_runtime(platform, executable)


def test_installed_runtime_path_allowed():
    probe.require_installed_runtime(
        'darwin', '/Applications/OK-WW Foreground Internal.app/Contents/MacOS/macos_main')


@pytest.mark.parametrize('failure', [None, 'stop', 'release', 'close'])
def test_cleanup_order_and_idempotence(tmp_path, monkeypatch, failure):
    monkeypatch.chdir(tmp_path)
    calls = []

    def operation(name):
        def run():
            calls.append(name)
            if failure == name:
                raise RuntimeError('simulated cleanup failure')
        return run

    interaction = SimpleNamespace(
        release_all=operation('release'), should_capture=lambda: False,
        held_state=SimpleNamespace(snapshot=lambda: SimpleNamespace(keys=(), buttons=())))
    capture = SimpleNamespace(close=operation('close'), diagnostics=lambda: SimpleNamespace(
        state=SimpleNamespace(value='closed')))
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._executor = SimpleNamespace(
        stop=operation('stop'), interaction=interaction,
        device_manager=SimpleNamespace(capture_method=capture))
    task.log_info = Mock()
    monkeypatch.setattr(probe.og, 'app', SimpleNamespace(quit=operation('quit')))
    task._finish('test')
    task._finish('again')
    assert calls == ['stop', 'release', 'close', 'quit']
    reports = list((tmp_path / 'logs').glob('macos-internal-probe-*.json'))
    assert len(reports) == 1
    report = probe.json.loads(reports[0].read_text())
    assert report['held_keys_after'] == report['held_buttons_after'] == 0
    assert report['capture_state_after'] == 'closed'
    assert bool(report['cleanup_errors']) is (failure is not None)


def test_loaded_probe_does_not_start_or_send_input():
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    assert task.enabled is False
    assert task._timer is None
    assert task.default_config == {'Mode': 'read-only', 'Delayed Start': ''}
    task.on_destroy()


def countdown_task():
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._executor = SimpleNamespace(exit_event=probe.threading.Event())
    task._handler = SimpleNamespace(post=Mock())
    task.ensure_device_capabilities = Mock()
    task.info_set = Mock()
    return task


def test_countdown_only_schedules_and_does_not_enable_or_access_provider():
    task = countdown_task()
    task.start_countdown()
    task.start_countdown()
    assert task.enabled is False
    task._handler.post.assert_called_once()
    assert task._handler.post.call_args.kwargs == {'delay': 1}
    callback = task._handler.post.call_args.args[0]
    callback()
    assert task._handler.post.call_count == 2
    assert task.enabled is False


@pytest.mark.parametrize('cancel', ['button', 'exit', 'destroy', 'enabled'])
def test_cancelled_countdown_never_dispatches(cancel):
    task = countdown_task()
    task.start_countdown()
    token = task._preparation
    if cancel == 'button':
        task.cancel_countdown()
    elif cancel == 'exit':
        task.executor.exit_event.set()
    elif cancel == 'destroy':
        task.on_destroy()
    else:
        task._enabled = True
    task._countdown_tick(token, 0)
    assert token.is_set()
    # The executor deliberately has no interaction: no provider can be touched.


def test_countdown_missing_target_does_not_start(monkeypatch):
    task = countdown_task()
    task.executor.interaction = SimpleNamespace(target=None)
    start = Mock()
    monkeypatch.setattr(probe.og, 'app', SimpleNamespace(start_controller=SimpleNamespace(start=start)))
    task.start_countdown()
    task._countdown_tick(task._preparation, 0)
    start.assert_not_called()
    assert not task.enabled


def test_dispatched_countdown_cannot_be_scheduled_again():
    task = countdown_task()
    task._start_requested = True
    task.start_countdown()
    task._handler.post.assert_not_called()


@pytest.mark.parametrize('challenge_found', [False, True])
def test_read_only_reports_features_on_same_frame_without_input(challenge_found):
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._report = {'ordinary_attempts': 0}
    frame = reference_frame(1920, 1080)
    task.ocr = Mock(return_value=[SimpleNamespace(name='private text not recorded')])
    task.find_one = Mock(side_effect=[SimpleNamespace(confidence=.951567),
                        SimpleNamespace(confidence=.987654) if challenge_found else None])
    input_methods = ('click', 'click_relative', 'send_key', 'send_key_down',
                     'send_key_up', 'click_team_challenge')
    for name in input_methods:
        setattr(task, name, Mock(side_effect=AssertionError('read-only must not send input')))
    task._probe_read_only(frame)
    task.ocr.assert_called_once_with(frame=frame, to_y=.85, log=False, screenshot=False)
    assert task.find_one.call_args_list == [
        ((name,), {'frame': frame, 'screenshot': False})
        for name in ('team_close', 'team_start_challenge')]
    assert task._report == {
        'ordinary_attempts': 0, 'ocr_count': 1, 'status': 'completed',
        'team_close_found': True, 'team_close_confidence': .9516,
        'team_start_challenge_found': challenge_found,
        **({'team_start_challenge_confidence': .9877} if challenge_found else {})}
    for name in input_methods:
        getattr(task, name).assert_not_called()


def direct_entry(name='直接挑战', confidence=.99, x=1170, y=500):
    return probe.Box(x, y, 70, 22, name=name, confidence=confidence)


@pytest.mark.parametrize('name', ['前往', '开启挑战', '挑战', '直接挑站', 'Fast Travel', ''])
def test_entry_never_substitutes_other_buttons(name):
    with pytest.raises(RuntimeError):
        probe.require_direct_challenge([direct_entry(name)], 1280, 800)


@pytest.mark.parametrize('boxes', [[], [direct_entry(), direct_entry(y=600)],
                                  [direct_entry(confidence=.89)], [direct_entry(confidence=float('nan'))],
                                  [direct_entry(x=300)], [direct_entry(y=750)]])
def test_entry_rejects_absent_ambiguous_low_confidence_or_unsafe_target(boxes):
    with pytest.raises(RuntimeError):
        probe.require_direct_challenge(boxes, 1280, 800)


@pytest.mark.parametrize('width,height', [(1280, 800), (1920, 1080), (1920, 1200)])
def test_entry_uses_native_ocr_coordinates_in_both_ratios(width, height):
    scale = width / 1280
    entry = probe.Box(1170 * scale, .6 * height, 70 * scale, 22 * scale,
                      name='直 接 挑 战', confidence=.99)
    assert probe.require_direct_challenge([entry], width, height) is entry
    probe.require_stable_entry(entry, entry, scale)
    with pytest.raises(RuntimeError):
        probe.require_stable_entry(entry, direct_entry(y=50), scale)


def entry_task(monkeypatch):
    """Task-method spies only; no native events, foreground mocks or guard changes."""
    from src.task.BaseWWTask import BaseWWTask
    diagnostics = SimpleNamespace(state=SimpleNamespace(value='running'), geometry=object(),
                                  target_generation=1, capture_generation=1,
                                  frame_age_seconds=.01, frames_published=1)
    manager = SimpleNamespace(capture_method=SimpleNamespace(diagnostics=lambda: diagnostics),
                              get_preferred_device=lambda: {'device': 'macos'})
    task = probe.MacInternalProbe(executor=SimpleNamespace(scene=None), app=None)
    task._executor = SimpleNamespace(device_manager=manager, exit_event=probe.threading.Event())
    task._report = {'status': 'running', 'ordinary_attempts': 0}
    task._deadline = probe.time.monotonic() + 15
    frame = reference_frame()

    def publish(*args):
        diagnostics.frames_published += 1
        return frame

    task.next_frame = Mock(side_effect=publish)
    task.sleep = Mock(side_effect=publish)
    task.ocr = Mock(side_effect=[material_labels(), material_labels(), [direct_entry()],
                                material_labels(), [direct_entry()]])
    task.find_one = Mock(return_value=None)
    task.click = Mock()
    task.wait_feature = Mock(return_value=probe.Box(0, 0, 1, 1, name='team_start_challenge'))
    category = Mock()
    monkeypatch.setattr(BaseWWTask, 'open_boss_book', category)
    for forbidden in ('click_team_challenge', 'wait_click_travel', 'send_key', 'send_key_down'):
        setattr(task, forbidden, Mock(side_effect=AssertionError('forbidden guide-entry action')))
    return task, frame, diagnostics, category


def test_entry_stops_after_production_destination_helper(monkeypatch):
    task, frame, _, category = entry_task(monkeypatch)
    task._probe_guide_entry(frame)
    category.assert_called_once_with(task, 'wuyin', after_sleep=1)
    task.click.assert_called_once_with(1205, 511, name='direct_challenge_entry', after_sleep=.2)
    task.wait_feature.assert_called_once_with(
        ['fast_travel_custom', 'gray_teleport', 'remove_custom', 'team_start_challenge'],
        time_out=10, settle_time=.5, raise_if_not_found=True)
    assert task._report['ordinary_attempts'] == 2
    assert task._report['entry_confirmations'] == 2
    assert task._report['status'] == 'team-ready'
    for forbidden in ('click_team_challenge', 'wait_click_travel', 'send_key', 'send_key_down'):
        getattr(task, forbidden).assert_not_called()


@pytest.mark.parametrize('case', ['no-entry', 'ambiguous', 'moved', 'already-team',
                                 'no-new-frame', 'geometry-change', 'timeout', 'stopped'])
def test_entry_failure_prevents_entry_click(monkeypatch, case):
    task, frame, diagnostics, _ = entry_task(monkeypatch)
    if case == 'no-entry':
        task.ocr.side_effect = [material_labels(), material_labels(), [direct_entry('前往')]]
    elif case == 'ambiguous':
        task.ocr.side_effect = [material_labels(), material_labels(), [direct_entry(), direct_entry(y=600)]]
    elif case == 'moved':
        task.ocr.side_effect = [material_labels(), material_labels(), [direct_entry()],
                                material_labels(), [direct_entry(y=600)]]
    elif case == 'already-team':
        task.find_one.return_value = probe.Box(0, 0, 1, 1, name='team_start_challenge')
    elif case == 'no-new-frame':
        task.sleep.side_effect = None
    else:
        def disturb(_duration):
            if case == 'geometry-change':
                diagnostics.capture_generation += 1  # Same dimensions, new stream.
            elif case == 'timeout':
                task._deadline = 0
            else:
                task.executor.exit_event.set()
        task.sleep.side_effect = disturb
    with pytest.raises(RuntimeError):
        task._probe_guide_entry(frame)
    task.click.assert_not_called()
    task.wait_feature.assert_not_called()


@pytest.mark.parametrize('case', ['wrong-page', 'stale-capture', 'closed-capture', 'finished'])
def test_entry_failure_before_category_produces_no_clicks(monkeypatch, case):
    task, frame, diagnostics, category = entry_task(monkeypatch)
    if case == 'wrong-page':
        task.ocr.side_effect = [[]]
    elif case == 'stale-capture':
        diagnostics.frame_age_seconds = 2
    elif case == 'closed-capture':
        diagnostics.state.value = 'closed'
    else:
        task._finished = True
    with pytest.raises(RuntimeError):
        task._probe_guide_entry(frame)
    category.assert_not_called()
    task.click.assert_not_called()


def test_entry_never_continues_from_travel_destination(monkeypatch):
    task, frame, _, _ = entry_task(monkeypatch)
    task.wait_feature.return_value = probe.Box(0, 0, 1, 1, name='gray_teleport')
    with pytest.raises(RuntimeError, match='Unexpected travel destination'):
        task._probe_guide_entry(frame)
    assert task.click.call_count == 1
    task.wait_click_travel.assert_not_called()
    task.click_team_challenge.assert_not_called()
