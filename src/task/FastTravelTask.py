import re
from ok import TriggerTask, Logger
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


class FastTravelTask(BaseWWTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': False}
        self.name = "Fast Travel"
        self.description = 'Auto Click Fast Travel in Map'
        self.match = [re.compile(r'Travel'), '快速旅行', '前往', 'Proceed']

    def run(self):
        travel = self.find_one('gray_teleport')
        if travel:
            results = self.ocr(
                box=self.box_of_screen(0.7, 0.89, 1, 1),
                match=self.match)

            if results:
                self.log_debug("has result")
                self.click_traval_button()
                return True
