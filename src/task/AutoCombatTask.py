from qfluentwidgets import FluentIcon

from ok.Task import TriggerTask
from ok.logging.Logger import get_logger
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
        self.last_is_click = False

    def run(self):
        while self.in_combat():
            try:
                logger.debug(f'autocombat loop {self.chars}')
                if self._in_realm:
                    self.realm_perform()
                else:
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

    def realm_perform(self):
        if not self.last_is_click:
            self.click()
        else:
            if self.available('liberation'):
                self.send_key_and_wait_animation(self.get_liberation_key(), self.in_realm_or_multi)
            elif self.available('echo'):
                self.send_key(self.get_echo_key())
            elif self.available('resonance'):
                self.send_key(self.get_resonance_key())
            elif self.is_con_full() and self.in_team()[0]:
                self.send_key_and_wait_animation('2', self.in_realm_or_multi)
        self.last_is_click = not self.last_is_click

    def trigger(self):
        if self.in_combat():
            self.load_chars()
            return True
