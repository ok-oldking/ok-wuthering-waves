from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException

logger = get_logger(__name__)


class AutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self):
        super().__init__()
        self.trigger_interval = 0.2
        self.name = "Auto Combat"
        self.description = "Enable auto combat in Abyss, Game World etc"

    def run(self):
        while self.in_combat():
            try:
                logger.debug(f'autocombat loop {self.chars}')
                self.get_current_char().perform()
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {e}')
                if self.debug:
                    self.screenshot(f'auto_combat_task_out_of_combat {e}')
                break

    def trigger(self):
        if self.in_combat():
            self.load_chars()
            return True
