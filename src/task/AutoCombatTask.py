from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TriggerTask import TriggerTask
from src.combat.CombatCheck import CombatCheck
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException

logger = get_logger(__name__)


class AutoCombatTask(BaseCombatTask, TriggerTask, FindFeature, OCR, CombatCheck):

    def run(self):
        while self.in_combat():
            try:
                logger.debug(f'autocombat loop {self.chars}')
                self.get_current_char().perform()
            except NotInCombatException:
                logger.info('out of combat break')
                break

    def trigger(self):
        if self.in_combat():
            self.load_chars()
            return True
