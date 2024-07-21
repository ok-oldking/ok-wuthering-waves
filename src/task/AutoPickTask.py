from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask

logger = get_logger(__name__)


class AutoPickTask(TriggerTask, FindFeature):

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
        f_search_box = self.get_box_by_name('pick_up_f')
        f_search_box = f_search_box.copy(x_offset=-f_search_box.width / 2,
                                         width_offset=f_search_box.width,
                                         height_offset=f_search_box.height * 4,
                                         y_offset=-f_search_box.height / 2,
                                         name='search_dialog')
        if f := self.find_one('pick_up_f', box=f_search_box,
                              threshold=0.8):
            dialog_search = f.copy(x_offset=f.width * 2, width_offset=f.width * 2, height_offset=f.height * 2,
                                   y_offset=-f.height,
                                   name='search_dialog')
            return self.find_one('dialog_3_dots', box=dialog_search,
                                 threshold=0.8) is None
