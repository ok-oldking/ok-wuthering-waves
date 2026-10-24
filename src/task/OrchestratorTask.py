"""Opt-in sidebar queue; original DailyTask and CLI indices remain unchanged."""
from src.task.DailyTask import DailyTask
from src.task.FarmEchoTask import FarmEchoTask
from src.task.GardenTask import GardenTask
from src.task.MergeEchoTask import MergeEchoTask
from src.task.NightmareNestTask import NightmareNestTask
from src.task.NaturalStamina import farm_current_stamina
from src.task.OrchestratorPlan import (PLAN_KEY, CONTROL_STEPS, entry_id, task_key,
                                      boss_run_limit, executor_busy, validate_plan)
from src.task.OrchestratorControl import close_selected_game, wait_seconds
from src.task.StepPipeline import StepPipeline
from src.task.WWOneTimeTask import WWOneTimeTask


class OrchestratorTask(StepPipeline, DailyTask):
    requires_initial_frame = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Orchestrator'
        self.description = 'Run only the selected steps, in their displayed order.'
        self.visible = False
        self.support_schedule_task = False
        self.show_create_shortcut = False
        self.default_config = dict(self.default_config)
        self.default_config.update({PLAN_KEY: [], 'Nightmare Nest Mode': 'Daily',
                                    'Extra Boss Run Limit': 3, 'Exit After Task': False})
        self.config_type = dict(self.config_type)
        for key in (PLAN_KEY, 'Exit After Task', 'Farm Nightmare Nest for Daily Echo',
                    'Additional Tasks to Run After Daily Task'):
            self.config_type[key] = {'hidden': True}
        self.config_type['Nightmare Nest Mode'] = {'type': 'drop_down', 'options': ['Daily', 'All']}
        self.config_type['Extra Boss Run Limit'] = {'min': 1, 'max': 100}
        self.config_description['Nightmare Nest Mode'] = 'Daily capture or all configured nests.'
        self.config_description['Extra Boss Run Limit'] = 'Boss Echo repeat count (1-100).'
        # No imports from daily configs or changes to global startup preferences.

    def load_config(self):
        super().load_config()
        self.config['Exit After Task'] = False

    def queue_run(self):
        from ok import og
        from ok.core.events import communicate
        if executor_busy(self.executor, og.app.start_controller):
            raise RuntimeError('Wait until other tasks finish')
        if not getattr(self.executor, 'supports_frame_independent_tasks', False):
            raise RuntimeError('This draft requires frame-independent task support in ok-script')
        validate_plan(self.config[PLAN_KEY], execution=True)
        self.info_clear()
        self.exit_after_task, self._paused, self._enabled = False, False, True
        try:
            if not self.executor.enqueue_onetime_task(self):
                raise RuntimeError('Orchestrator task is not registered')
            self.executor.start()
        except Exception:
            self.disable()
            raise
        communicate.task.emit(self)

    def screenshot(self, name=None, frame=None, show_box=False, frame_box=None):
        # Cleanup must not wait for a capture after the game was closed.
        image = frame if frame is not None else getattr(self.executor, '_frame', None)
        if image is not None:
            from ok.core.events import communicate
            communicate.screenshot.emit(image, name, show_box, frame_box)

    def _open_game(self):
        from ok import og
        self.executor.device_manager.do_refresh(True)
        if not og.app.start_controller.start_device(initial_refresh_done=True):
            raise RuntimeError('Native launcher could not open the game')

    def _close_game(self):
        close_selected_game(self.executor.device_manager)

    def _prepare_gameplay(self):
        manager = self.executor.device_manager
        manager.do_refresh(True)
        if not manager.capture_method or not manager.capture_method.connected():
            raise RuntimeError('Game is not open; add an Open game step first')
        WWOneTimeTask.run(self)
        self.logged_in = False
        self.ensure_main(time_out=180)

    def validate_config(self, key, value):
        try:
            if key == PLAN_KEY:
                validate_plan(value, allow_empty=True)
            elif key == 'Extra Boss Run Limit':
                boss_run_limit(value)
        except ValueError as exc:
            return str(exc)
        return None

    def run(self):
        plan = validate_plan(self.config.get(PLAN_KEY, []), execution=True)
        if any(task_key(entry) == 'Farm4CEcho' for entry in plan):
            boss_run_limit(self.config.get('Extra Boss Run Limit', 3))
            if self.get_task_by_class(FarmEchoTask).config.get('Teleport to Boss', 'No') == 'No':
                raise ValueError('Enable Teleport to Boss in the boss task settings')
        if any(task_key(entry) == 'NightmareNest' for entry in plan) and self.config['Nightmare Nest Mode'] == 'All':
            if not self.get_task_by_class(NightmareNestTask).config.get('Which to Farm'):
                raise ValueError('Select at least one Nightmare Nest')
        self.pipeline_reset()
        steps = {
            'NightmareNest': (lambda: self._step_nightmare(self.config.get('Nightmare Nest Mode') == 'All'), False),
            'FarmStamina': (self._step_stamina, True),
            'ClaimDaily': (self.claim_daily, True),
            'ClaimMail': (self.claim_mail, False),
            'ClaimBattlePass': (self.claim_battle_pass, False),
            'WeeklyGarden': (self._step_garden, False),
            'MergeEcho': (self._step_merge, False),
            'Farm4CEcho': (self._step_boss, False),
        }
        prepared, login_failed, quit_requested = False, False, False
        for entry in plan:
            name, identity = task_key(entry), entry_id(entry)
            wait_seconds(self, 0)
            if name in CONTROL_STEPS:
                if name == 'OpenGame':
                    opened = self.step(identity, self._open_game)
                    prepared, login_failed = False, not opened
                elif name == 'CloseGame':
                    self.step(identity, self._close_game)
                    prepared, login_failed = False, False
                elif name == 'Wait':
                    self.step(identity, wait_seconds, self, entry['seconds'])
                else:
                    self._set_status(identity, 'success')
                    quit_requested = True
                continue
            if not prepared and not login_failed:
                prepared = self.step('Login', self._prepare_gameplay)
                login_failed = not prepared
            if login_failed:
                self._set_status(identity, 'skipped')
                continue
            function, required = steps[name]
            self.step(identity, function, required=required)
        try:
            self.pipeline_finish()
        finally:
            if quit_requested:
                from ok.core.events import communicate
                communicate.quit.emit()

    def _step_nightmare(self, farm_all):
        child = self.get_task_by_class(NightmareNestTask)
        had_override = 'ensure_main' in child.__dict__
        old_override = child.__dict__.get('ensure_main')
        try:
            child.ensure_main = lambda *args, **kwargs: None
            if farm_all:
                self.run_task_by_class(NightmareNestTask)
            else:
                child.run_capture_mode()
        finally:
            if had_override:
                child.ensure_main = old_override
            else:
                child.__dict__.pop('ensure_main', None)
        self.ensure_main(time_out=60)

    def _step_stamina(self):
        farm_current_stamina(self)
        self.sleep(4)

    def _step_garden(self):
        child = self.get_task_by_class(GardenTask)
        child.open_garden_weekly_page()
        if not child.is_weekly_garden_completed():
            self.run_task_by_class(GardenTask)
        self.ensure_main(time_out=60)

    def _step_merge(self):
        child = self.get_task_by_class(MergeEchoTask)
        saved = child.notify_if_not_enough
        try:
            child.notify_if_not_enough = False
            self.run_task_by_class(MergeEchoTask)
        finally:
            child.notify_if_not_enough = saved
        self.ensure_main(time_out=60)

    def _step_boss(self):
        child = self.get_task_by_class(FarmEchoTask)
        saved_config = child.config
        had_liberation = hasattr(child, 'use_liberation')
        saved_liberation = getattr(child, 'use_liberation', None)
        try:
            child.config = dict(saved_config)
            child.config['Repeat Farm Count'] = boss_run_limit(self.config.get('Extra Boss Run Limit', 3))
            WWOneTimeTask.run(child)
            child.use_liberation = child.config.get('Use Liberation')
            child.do_run()
        finally:
            child.config = saved_config
            if had_liberation:
                child.use_liberation = saved_liberation
            else:
                child.__dict__.pop('use_liberation', None)
        self.ensure_main(time_out=60)
