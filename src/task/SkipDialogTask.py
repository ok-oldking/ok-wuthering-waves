from ok import TriggerTask
from ok import get_logger
from src.task.SkipBaseTask import SkipBaseTask

logger = get_logger(__name__)


class AutoDialogTask(TriggerTask, SkipBaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.skip = None
        self.trigger_interval = 1
        self.name = "Skip Dialog during Quests"

    def run(self):
        pass

    def trigger(self):
        self.check_skip()
