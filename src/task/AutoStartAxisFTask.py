import time

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


class AutoStartAxisFTask(TriggerTask, BaseWWTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Start Axis on F"
        self.description = "Detect the F interaction icon outside combat and press F to start the combat axis"
        self.icon = FluentIcon.FLAG
        self.trigger_interval = 1
        self.last_auto_start_axis_f_time = 0
        self.default_config.update({
            '_enabled': False,
            'Axis Start Delay Seconds': 1.0,
        })
        self.config_description = {
            'Axis Start Delay Seconds': 'After pressing F, wait this many seconds, then start the custom axis immediately without waiting for combat detection.',
        }
        self.config_type = {
            'Axis Start Delay Seconds': {
                'min': 0,
            },
        }

    def _find_auto_start_axis_f(self):
        return self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box, threshold=0.8)

    def _known_in_combat(self):
        if self.scene is None:
            return False
        return bool(self.scene.in_combat())

    def run(self):
        if not self.scene.in_team(self.in_team_and_world):
            return False
        if self._known_in_combat():
            return False
        now = time.time()
        if now - self.last_auto_start_axis_f_time < 1:
            return False
        if not self._find_auto_start_axis_f():
            return False
        self.last_auto_start_axis_f_time = now
        logger.info('auto start axis from F icon')
        self.send_key('f')
        self._wait_before_start_axis()
        self._start_axis_without_waiting_for_combat()
        return True

    def _wait_before_start_axis(self):
        try:
            delay = max(0, float(self.config.get('Axis Start Delay Seconds', 1.0)))
        except (TypeError, ValueError):
            delay = 1.0
        if delay > 0:
            self.sleep(delay)

    def _start_axis_without_waiting_for_combat(self):
        try:
            from src.task.TeamAxisAutoCombatTask import TeamAxisAutoCombatTask
            combat_task = self.get_task_by_class(TeamAxisAutoCombatTask)
        except Exception as e:
            logger.error(f'auto start axis can not get combat task', e)
            return False
        if combat_task is None:
            return False
        return combat_task.run_custom_axis_from_f_start()
