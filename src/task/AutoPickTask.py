from qfluentwidgets import FluentIcon

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
        self.icon = FluentIcon.SHOPPING_CART

    def run(self):
        self.send_key('f')
        self.sleep(0.2)
        self.send_key('f')
        self.sleep(0.2)
        self.send_key('f')
        self.sleep(0.2)

    def trigger(self):
        if f := self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box,
                              threshold=0.8):
            dialog_search = f.copy(x_offset=f.width * 2, width_offset=f.width * 2, height_offset=f.height * 2,
                                   y_offset=-f.height,
                                   name='search_dialog')
            dialog_3_dots = self.find_feature('dialog_3_dots', box=dialog_search,
                                              threshold=0.8)
            if dialog_3_dots and self.absorb_echo_text:
                search_absorb = dialog_3_dots[0].copy(x_offset=f.width * 2, width_offset=f.width * 6,
                                                      height_offset=1.4 * f.height,
                                                      y_offset=-0.7 * f.height)
                # absorb = self.find_one(self.absorb_echo_feature, box=search_absorb, canny_lower=75, canny_higher=150,
                #                        threshold=0.65)
                absorb = self.ocr(box=search_absorb, match=self.absorb_echo_text, log=True, target_height=540)
                logger.debug(f'auto_pick try to search for absorb {self.absorb_echo_text} {absorb}')
                if absorb:
                    return True
            if not dialog_3_dots:
                return True
