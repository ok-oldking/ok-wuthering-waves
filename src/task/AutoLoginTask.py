from ok import TriggerTask, Logger
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask
from src.task.task_icons import task_icon

logger = Logger.get_logger(__name__)


class AutoLoginTask(BaseWWTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 5
        self.name = "🔑 Auto Login"
        self.icon = task_icon('login')
        self.description = "Auto Login After Game Starts"

    def run(self):
        if self.logged_in:
            pass
        elif self.scene.in_team(self.in_team_and_world):
            self.logged_in = True
        else:
            return self.wait_login()
