from qfluentwidgets import FluentIcon

from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException

logger = get_logger(__name__)


class MultiplayerAutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self):
        super().__init__()
        self.default_config = {'_enabled': False}
        self.trigger_interval = 0.1
        self.name = "Auto Combat in Multiplayer Mode"
        self.description = "Enable auto combat in Multiplayer Mode"
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False

    def check_not_in_animation(self):
        return self.in_multiplayer()

    def run(self):
        while self.in_multiplayer() and self.in_combat(check_team=False):
            try:
                logger.debug(f'multiplayer combat loop')
                self.perform()
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {e}')
                if self.debug:
                    self.screenshot(f'auto_combat_task_out_of_combat {e}')
                break

    def perform(self):
        if not self.last_is_click:
            self.click()
        else:
            if self.available('liberation'):
                self.send_key_and_wait_animation(self.get_liberation_key(), self.check_not_in_animation)
            elif self.available('echo'):
                self.send_key(self.get_echo_key())
            elif self.available('resonance'):
                self.send_key(self.get_resonance_key())
        self.last_is_click = not self.last_is_click

    def trigger(self):
        if self.in_multiplayer() and self.in_combat(check_team=False):
            return True
