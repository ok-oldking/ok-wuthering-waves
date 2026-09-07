"""Opt-in internal acceptance task loaded by the packaged app's ok_tasks loader.

This is not a new supported game task. It never starts itself, changes another
task's preferences, substitutes a provider, or opens the foreground guard.
"""
import json
import hashlib
from pathlib import Path
import sys
import threading
import time

from ok import BaseTask, Box, og
from ok.device.capabilities import DeviceCapabilities

# Capture identity when this external module is loaded, not at report time.
PROBE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def probe_requirements(mode):
    if mode == 'autopick-once':
        return DeviceCapabilities(keyboard_tap=True, scroll=True, foreground_only=True)
    if mode == 'read-only':
        return DeviceCapabilities(foreground_only=True)
    if mode == 'hold-focus':
        return DeviceCapabilities(keyboard_hold=True, foreground_only=True)
    if mode in ('guide-category', 'guide-entry'):
        return DeviceCapabilities(absolute_mouse=True, mouse_left=True, foreground_only=True)
    raise ValueError('Unknown internal probe mode')


def probe_geometry(frame):
    # Match the app's two supported ratios and minimum size. Acceptance examples
    # are not a fixed-resolution requirement; never resample the captured frame.
    if len(frame.shape) != 3 or frame.shape[2] != 3 or str(frame.dtype) != 'uint8':
        raise RuntimeError('Unexpected real content geometry')
    height, width = frame.shape[:2]
    if width < 1280 or height < 720 or not any(
            abs(width / height - ratio) <= .01 for ratio in (16 / 9, 16 / 10)):
        raise RuntimeError('Unsupported probe aspect ratio or minimum size')
    scale = width / 1280
    return scale, Box(0, 0, round(460 * scale), min(height, round(760 * scale)))


def require_material_page(boxes, scale=1):
    """Strict Chinese reference-page precondition; do not guess an unknown page."""
    required = ('素材获取', '无音清剿', '残象聚落')
    found = {}
    for name in required:
        matches = [box for box in boxes if ''.join(box.name.split()) == name]
        if len(matches) != 1:
            raise RuntimeError('Expected material guide page is not unambiguous')
        found[name] = matches[0]
    if not (found['素材获取'].y < 100 * scale and
            400 * scale < found['无音清剿'].y < found['残象聚落'].y < 730 * scale):
        raise RuntimeError('Unexpected material guide layout')
    return found


def require_installed_runtime(platform, executable):
    path = Path(executable)
    if platform != 'darwin' or path.parent != Path(
            '/Applications/OK-WW Foreground Internal.app/Contents/MacOS'):
        raise RuntimeError('Run this probe inside the installed internal app only')


def require_direct_challenge(boxes, width, height):
    """Chinese-only acceptance fixture: never substitute a travel/start button."""
    matches = [box for box in boxes if ''.join((box.name or '').split()) == '直接挑战']
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one direct-challenge entry')
    box = matches[0]
    if not (.9 <= float(box.confidence) <= 1 and
            .84 * width <= box.x < box.x + box.width <= .98 * width and
            .18 * height <= box.y < box.y + box.height <= .88 * height):
        raise RuntimeError('Uncertain direct-challenge entry or unsafe position')
    return box


def require_stable_entry(first, second, scale):
    if any(abs(getattr(first, field) - getattr(second, field)) > 6 * scale
           for field in ('x', 'y', 'width', 'height')):
        raise RuntimeError('Direct-challenge entry moved between frames')


def require_safe_pickup(boxes):
    matches = [box for box in boxes if ''.join((box.name or '').split()) == '紫珊瑚'
               and float(box.confidence) >= 0.9]
    if len(matches) != 1:
        raise RuntimeError('Expected one confirmed safe purple-coral pickup prompt')
    return matches[0]


class MacInternalProbe(BaseTask):
    """Experimental, manually started read-only or four-second W focus probe."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '内部短验收 / Internal Probe (experimental)'
        self.description = '仅内部验收 / Internal only；关闭其他任务。read-only 无输入；hold-focus 最多 W 四秒；guide-category 单次分类；guide-entry 只进入准备页，15 秒退出。'
        self.default_config = {'Mode': 'read-only'}
        self.default_config['Delayed Start'] = ''
        self.config_description = {'Mode': 'read-only：OCR；hold-focus：W 失焦；guide-category：单次分类；guide-entry：中文素材页到准备页 / Chinese guide to team page only，最多两次点击、15 秒停止，不开启挑战或传送。测试后正常退出。'}
        self.config_type = {'Mode': {'type': 'drop_down', 'options': ['read-only', 'hold-focus', 'guide-category', 'guide-entry', 'autopick-once']}}
        self.description += ' autopick-once：10秒内仅测试已确认的紫珊瑚 / confirmed coral only.'
        self.config_description['Mode'] += ' autopick-once：调用正式 AutoPickTask 一轮（内部最多三次 F），随后退出；不代表持续 Trigger 调度验收。'
        self.config_description['Delayed Start'] = '请用此按钮而非任务开始：8秒内切回游戏并松开 Option / Switch to game within 8 seconds; release Option.'
        self.config_type['Delayed Start'] = {'type': 'button', 'buttons': [
            {'text': '8秒后启动 / Start in 8s', 'callback': self.start_countdown},
            {'text': '取消倒计时 / Cancel', 'callback': self.cancel_countdown}]}
        self._preparation = None
        self._start_requested = False
        self.support_schedule_task = False
        self._finish_lock = threading.Lock()
        self._finished = False
        self._timer = None
        self._deadline = None
        self._report = {}

    def get_required_capabilities(self):
        return probe_requirements((self.config or self.default_config)['Mode'])

    def cancel_countdown(self):
        if self._preparation is not None:
            self._preparation.set()
        self.info_set('Preparation / 准备', 'Cancelled / 已取消')

    def disable(self):
        self.cancel_countdown()
        super().disable()

    def start_countdown(self):
        # Qt callback only schedules work. Never block the GUI or arm input here.
        if self._start_requested:
            return  # One dispatch per probe instance; restart after startup failure.
        if self.enabled or self.executor.exit_event.is_set():
            raise RuntimeError('Stop the current task before preparing a new probe')
        if self._preparation is not None and not self._preparation.is_set():
            return
        self.ensure_device_capabilities()
        token = threading.Event()
        self._preparation = token
        self.info_set('Preparation / 准备', '8s: switch to game / 请切回游戏')
        self.handler.post(lambda: self._countdown_tick(token, 7), delay=1)

    def _countdown_tick(self, token, remaining):
        if token.is_set() or self.executor.exit_event.is_set() or self.enabled:
            token.set()
            return
        if remaining:
            self.info_set('Preparation / 准备', f'{remaining}s')
            self.handler.post(lambda: self._countdown_tick(token, remaining - 1), delay=1)
            return
        # Read-only precondition, never activate or open the guard ourselves.
        # The controller then repeats the normal capability/readiness/on_run path.
        target = getattr(self.executor.interaction, 'target', None)
        if target is None or not target.is_foreground():
            token.set()
            self.info_set('Preparation / 准备', 'Not foreground: not started / 游戏未置前，未启动')
            return
        self.ensure_device_capabilities()
        if token.is_set() or self.executor.exit_event.is_set():
            return
        self._start_requested = True
        token.set()
        og.app.start_controller.start(self)

    def ensure_device_capabilities(self):
        # Keep the framework's actual capability gate, including execution-time
        # rechecks. Reject coexistence instead of changing persisted preferences.
        super().ensure_device_capabilities()
        require_installed_runtime(sys.platform, sys.executable)
        if any(task is not self and task.enabled for task in self.executor.get_all_tasks()):
            raise RuntimeError('Disable all other tasks before the internal probe')

    def _finish(self, reason):
        with self._finish_lock:
            if self._finished:
                return
            self._finished = True
        if self._timer is not None:
            self._timer.cancel()
        interaction = self.executor.interaction
        capture = self.executor.device_manager.capture_method
        cleanup_errors = []
        # Same shutdown order as the production app. Each step still runs if a
        # preceding cleanup operation fails; never force-kill the native runtime.
        for name, operation in (
                ('executor_stop', self.executor.stop),
                ('release_all', interaction.release_all),
                ('capture_close', capture.close)):
            try:
                result = operation()
                if result is False:
                    cleanup_errors.append(name)
            except Exception:
                cleanup_errors.append(name)
        try:
            held = interaction.held_state.snapshot()
            self._report.update(
                finish_reason=reason, held_keys_after=len(held.keys),
                held_buttons_after=len(held.buttons),
                guard_open_after=interaction.should_capture(),
                capture_state_after=capture.diagnostics().state.value,
                cleanup_errors=cleanup_errors)
            # Counts and state codes only: no image, OCR text, account identifier,
            # absolute user path, PID, or exception message in the report.
            destination = Path('logs') / ('macos-internal-probe-' + str(time.time_ns()) + '.json')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(self._report, ensure_ascii=False, indent=2), encoding='utf-8')
            self.log_info('MAC_INTERNAL_PROBE ' + json.dumps(self._report))
        finally:
            og.app.quit()  # App.quit queues the Qt quit on the GUI thread.

    def _probe_guide_category(self, frame):
        from src.task.BaseWWTask import BaseWWTask

        # Absolute frame-local ROI; excludes the right-side action buttons and
        # bottom account area. OCR text/images are never saved by this probe.
        scale, region = probe_geometry(frame)
        labels = require_material_page(self.ocr(
            frame=frame, box=region, log=False, screenshot=False), scale)
        self._report['category_label_y'] = {
            'wuyin': labels['无音清剿'].y, 'canxiang': labels['残象聚落'].y}
        self._report['ordinary_attempts'] += 1
        # Exercise the installed task method unchanged. It only performs one
        # left-side category click; never call the target/challenge helpers.
        BaseWWTask.open_boss_book(self, 'wuyin', after_sleep=1)
        self.next_frame()
        after = self.frame
        if after.shape != frame.shape:
            raise RuntimeError('Geometry changed during the category probe')
        self._report['material_page_after'] = bool(require_material_page(self.ocr(
            frame=after, box=region, log=False, screenshot=False), scale))
        for name in ('team_close', 'team_start_challenge'):
            found = self.find_one(name)
            self._report[name + '_found'] = bool(found)
            if found:
                self._report[name + '_confidence'] = round(float(found.confidence), 4)
        # These features do NOT establish which category is selected. Verify the
        # highlighted row visually after cleanup; never claim navigation passed.
        self._report['status'] = 'observed-not-accepted'

    def _probe_read_only(self, frame):
        # Same captured frame for OCR and templates; no navigation or input.
        # Exclude bottom account-ID area. Text is deliberately not saved.
        boxes = self.ocr(frame=frame, to_y=0.85, log=False, screenshot=False)
        self._report.update(ocr_count=len(boxes), status='completed' if boxes else 'no-text')
        for name in ('team_close', 'team_start_challenge'):
            found = self.find_one(name, frame=frame, screenshot=False)
            self._report[name + '_found'] = bool(found)
            if found:
                self._report[name + '_confidence'] = round(float(found.confidence), 4)

    def _probe_autopick_once(self, frame):
        from src.task.AutoPickTask import AutoPickTask

        height, width = frame.shape[:2]
        region = Box(round(width * .66), round(height * .44),
                     round(width * .20), round(height * .20))
        def labels(current):
            return self.ocr(frame=current, box=region, log=False, screenshot=False)
        require_safe_pickup(labels(frame))
        self.next_frame()
        if self.frame.shape != frame.shape:
            raise RuntimeError('Pickup geometry changed')
        require_safe_pickup(labels(self.frame))
        self._report['pickup_prompt_before'] = True
        # Framework composition path: the registered, unchanged AutoPickTask
        # instance checks its own capabilities and uses its production helpers.
        self._report['production_task_invoked'] = 'AutoPickTask'
        self.run_task_by_class(AutoPickTask)
        self.sleep(.5)
        self.next_frame()
        self._report['pickup_prompt_after'] = any(
            '紫珊瑚' in (box.name or '') for box in labels(self.frame))
        self._report['status'] = 'observed-not-accepted'
        # A match is evidence for manual review, not automatic task acceptance.

    def _uses_macos_provider(self):
        # Delegate the exact production predicate needed by wait_book_destination,
        # without inheriting unrelated combat hooks or changing capability gates.
        from src.task.BaseWWTask import BaseWWTask
        return BaseWWTask._uses_macos_provider(self)

    def _check_entry_active(self):
        if (self._finished or self._deadline is None or
                time.monotonic() >= self._deadline or self.executor.exit_event.is_set()):
            raise RuntimeError('Guide-entry probe stopped or timed out')

    def _entry_capture_state(self):
        self._check_entry_active()
        diagnostics = self.executor.device_manager.capture_method.diagnostics()
        if (diagnostics.state.value != 'running' or diagnostics.geometry is None or
                diagnostics.frame_age_seconds is None or diagnostics.frame_age_seconds > 1):
            raise RuntimeError('Guide-entry requires a healthy fresh capture')
        return ((diagnostics.target_generation, diagnostics.capture_generation, diagnostics.geometry),
                diagnostics.frames_published)

    def _entry_frame(self, epoch, shape, previous_sequence=None):
        before, sequence = self._entry_capture_state()
        if before != epoch or (previous_sequence is not None and sequence <= previous_sequence):
            raise RuntimeError('Capture changed or no newer frame available')
        # Keep acquisition through the normal task API; diagnostic counters only
        # prove a newer publication preceded this read, never replace its frame.
        frame = self.next_frame()
        if frame is None or frame.shape != shape:
            raise RuntimeError('Guide-entry frame unavailable or resized')
        probe_geometry(frame)
        after, sequence = self._entry_capture_state()
        if after != epoch:
            raise RuntimeError('Capture changed during frame acquisition')
        return frame, sequence, time.monotonic()

    def _entry_target(self, frame):
        scale, region = probe_geometry(frame)
        require_material_page(self.ocr(frame=frame, box=region, log=False, screenshot=False), scale)
        if self.find_one('team_start_challenge', frame=frame, screenshot=False):
            raise RuntimeError('Already on a preparation page; do not click')
        height, width = frame.shape[:2]
        actions = Box(round(.84 * width), round(.18 * height),
                      round(.14 * width), round(.70 * height))
        boxes = self.ocr(frame=frame, box=actions, log=False, screenshot=False)
        return require_direct_challenge(boxes, width, height)

    def _probe_guide_entry(self, frame):
        from src.task.BaseWWTask import BaseWWTask

        if not self._uses_macos_provider():
            raise RuntimeError('Guide-entry requires the production macOS provider')
        epoch, _ = self._entry_capture_state()
        shape = frame.shape
        initial, _, _ = self._entry_frame(epoch, shape)
        scale, region = probe_geometry(initial)
        require_material_page(self.ocr(frame=initial, box=region, log=False, screenshot=False), scale)
        if self._entry_capture_state()[0] != epoch:
            raise RuntimeError('Capture changed before category click')
        self._report['ordinary_attempts'] += 1
        BaseWWTask.open_boss_book(self, 'wuyin', after_sleep=1)

        first_frame, first_sequence, _ = self._entry_frame(epoch, shape)
        first = self._entry_target(first_frame)
        self.sleep(.15)
        second_frame, _, observed_at = self._entry_frame(epoch, shape, first_sequence)
        second = self._entry_target(second_frame)
        require_stable_entry(first, second, scale)
        if self._entry_capture_state()[0] != epoch or time.monotonic() - observed_at > 1:
            raise RuntimeError('Capture changed or entry observation expired before click')
        self._report['entry_confirmations'] = 2
        self._report['ordinary_attempts'] += 1
        # Click the current OCR centre in real frame pixels. Production Quartz
        # performs the final foreground/generation checks. No travel fallback.
        self.click(round(second.x + second.width / 2), round(second.y + second.height / 2),
                   name='direct_challenge_entry', after_sleep=.2)
        self._check_entry_active()
        if not BaseWWTask.wait_book_destination(self):
            raise RuntimeError('Unexpected travel destination; do not continue')
        self._check_entry_active()
        if self._entry_capture_state()[0] != epoch:
            raise RuntimeError('Capture changed while waiting for preparation page')
        self._report.update(status='team-ready', destination_helper='wait_book_destination',
                            team_start_challenge_found=True)
        # End here. Never call click_team_challenge, claim, navigation or combat.

    def run(self):
        self.ensure_device_capabilities()
        mode = self.config['Mode']
        self._report = {'mode': mode, 'status': 'running', 'ordinary_attempts': 0,
                        'probe_sha256': PROBE_SHA256}
        # Independent fail-safe also covers a blocked next_frame/OCR operation.
        # Startup itself sends no ordinary input and keeps its own normal timeout.
        limit = 15 if mode == 'guide-entry' else 10
        self._deadline = time.monotonic() + limit
        self._timer = threading.Timer(limit, self._finish, args=('timeout',))
        self._timer.daemon = True
        self._timer.start()
        try:
            self.next_frame()
            frame = self.frame
            self._report.update(frame_shape=list(frame.shape), frame_dtype=str(frame.dtype))
            probe_geometry(frame)
            if mode == 'read-only':
                self._probe_read_only(frame)
            elif mode == 'guide-category':
                self._probe_guide_category(frame)
            elif mode == 'guide-entry':
                self._probe_guide_entry(frame)
            elif mode == 'autopick-once':
                self._probe_autopick_once(frame)
            else:
                interaction = self.executor.interaction
                self._report['ordinary_attempts'] += 1
                self.send_key_down('w')
                held = interaction.held_state.snapshot()
                self._report['held_keys_during'] = len(held.keys)
                if len(held.keys) != 1 or held.buttons:
                    raise RuntimeError('Expected exactly one owned key')
                self.log_info('MAC_INTERNAL_HELD_W')
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline and not self.executor.exit_event.is_set():
                    if not interaction.should_capture():
                        self._report['focus_gate_closed'] = True
                        held = interaction.held_state.snapshot()
                        self._report['held_keys_after_invalidation'] = len(held.keys)
                        # Stop here: task-level input may deliberately wait while
                        # paused. Never rearm it or bypass that pause to force an
                        # additional negative test into a different application.
                        self._report['status'] = 'focus-observed'
                        break
                    self.executor.exit_event.wait(0.02)
                else:
                    self._report['status'] = 'focus-not-observed'
        except Exception as error:
            self._report.update(status='failed', error_type=type(error).__name__)
            raise
        finally:
            self._finish('task-finally')

    def on_destroy(self):
        # Do not start cleanup for a probe that was merely loaded, not run.
        if self._preparation is not None:
            self._preparation.set()
        if self._timer is not None:
            self._timer.cancel()
