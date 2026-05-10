from ok import TriggerTask, Logger
from src.task.SkipBaseTask import SkipBaseTask

logger = Logger.get_logger(__name__)


class AutoDialogTask(TriggerTask, SkipBaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.skip = None
        self.trigger_interval = 0.5
        self.name = "Skip Dialog during Quests"

    def run(self):
        if self.scene.in_team(self.in_team_and_world):
            return
        if self.check_skip():
            return
        if self.skip_message():
            return

    def skip_message(self):
        if self.find_one('message'):
            if message_dialog := self.find_one('message_dialog', vertical_variance=0.4):
                click = message_dialog.copy(y_offset=2.5* message_dialog.height)
                click.width = self.width_of_screen(0.63)
                self.click(click, after_sleep=0.2)
                self.log_info(f'click {click}')
