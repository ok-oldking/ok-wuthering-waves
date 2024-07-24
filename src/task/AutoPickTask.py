from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask
from src.task.BaseWWTask import BaseWWTask

logger = get_logger(__name__)


class AutoPickTask(TriggerTask, BaseWWTask, FindFeature):

    def __init__(self):
        super().__init__()
        self.name = "Auto Pick"
        self.description = "Auto Pick Flowers in Game World"

    def run(self):
        self.send_key('f')
        self.sleep(0.2)
        self.send_key('f')
        self.sleep(0.2)
        self.send_key('f')
        self.sleep(0.2)

    def trigger(self):
        if f := self.find_one('pick_up_f', box=self.f_search_box,
                              threshold=0.8):
            dialog_search = f.copy(x_offset=f.width * 2, width_offset=f.width * 2, height_offset=f.height * 2,
                                   y_offset=-f.height,
                                   name='search_dialog')
            return self.find_one('dialog_3_dots', box=dialog_search,
                                 threshold=0.8) is None
