from qfluentwidgets import FluentIcon

from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

logger = get_logger(__name__)


class AutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self):
        super().__init__()
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.name = "Auto Combat"
        self.description = "Enable auto combat in Abyss, Game World etc"
        self.icon = FluentIcon.CALORIES

    def run(self):
        while self.in_combat():
            try:
                logger.debug(f'autocombat loop {self.chars}')
                self.get_current_char().perform()
            except CharDeadException:
                logger.info(f'char dead try teleport to heal')
                try:
                    self.teleport_to_heal()
                except Exception as e:
                    logger.error('teleport to heal error', e)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {e}')
                if self.debug:
                    self.screenshot(f'auto_combat_task_out_of_combat {e}')
                break

    def trigger(self):
        if self.in_combat():
            self.load_chars()
            return True
