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
        self.default_config.update({
            '_enabled': True,
            'Pick Up White List': ['吸收', 'Absorb'],
            'Pick Up Black List': ['开始合成']
        })

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
            dialog_search = f.copy(x_offset=f.width * 3, width_offset=f.width * 2, height_offset=f.height * 2,
                                   y_offset=-f.height,
                                   name='search_dialog')

            text_area = dialog_search.copy(x_offset=dialog_search.width, width_offset=f.width * 6,
                                           height_offset=0,
                                           y_offset=0)
            dialog_3_dots = self.find_feature('dialog_3_dots', box=dialog_search,
                                              threshold=0.8)

            if dialog_3_dots:
                if self.config.get('Pick Up White List'):
                    texts = self.ocr(box=text_area, match=self.config.get('Pick Up White List'), log=True,
                                     target_height=540)
                    if texts:
                        logger.info(f'found Pick Up White List {texts}')
                        return True
            else:
                if self.config.get('Pick Up Black List'):
                    texts = self.ocr(box=text_area, match=self.config.get('Pick Up Black List'), log=True,
                                     target_height=540)
                    if texts:
                        logger.info(f'found Pick Up Black List: {texts}')
                        return False
                return True
