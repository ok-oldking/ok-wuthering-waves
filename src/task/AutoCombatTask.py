from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger
from src.scene.WWScene import WWScene
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

logger = Logger.get_logger(__name__)


class AutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.name = "Auto Combat"
        self.description = "Enable auto combat in Abyss, Game World etc"
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False
        self.scene: WWScene | None = None
        self.default_config.update({
            'Auto Target': True,
        })
        self.config_description = {
            'Auto Target': 'Turn off to enable auto combat only when manually target enemy using middle click'
        }

    def run(self):
        ret = False
        if not self.scene.in_team(self.in_team_and_world):
            return ret
        while self.in_combat():
            ret = True
            try:
                self.get_current_char().perform()
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {e}')
                # if self.debug:
                #     self.screenshot(f'auto_combat_task_out_of_combat {e}')
                break
        if ret:
            self.combat_end()
        return ret
