from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


class AutoLoginTask(BaseWWTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 5
        self.name = "Auto Login"
        self.description = "Auto Login After Game Starts"
        self.icon = FluentIcon.ACCEPT
        self.scene: WWScene | None = None

    def run(self):
        if self._logged_in:
            pass
        elif self.scene.in_team(self.in_team_and_world):
            self._logged_in = True
        else:
            return self.wait_login()
