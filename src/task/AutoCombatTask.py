from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException

logger = get_logger(__name__)


class AutoCombatTask(BaseCombatTask):

    def run(self):
        while self.in_combat():
            try:
                logger.debug(f'autocombat loop {self.chars}')
                self.get_current_char().perform()
            except NotInCombatException as e:
                logger.info(f'out of combat break {e}')
                if self.debug:
                    self.screenshot(f'out of combat break {e}')
                break

    def trigger(self):
        if self.in_combat():
            self.load_chars()
            return True
