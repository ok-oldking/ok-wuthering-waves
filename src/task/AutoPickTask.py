import time

from qfluentwidgets import FluentIcon

from ok import FindFeature, Logger
from ok import TriggerTask
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask, f_white_color

logger = Logger.get_logger(__name__)


class AutoPickTask(TriggerTask, BaseWWTask, FindFeature):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Pick"
        self.description = "Auto Pick Flowers in Game World"
        self.icon = FluentIcon.SHOPPING_CART
        self.scene: WWScene | None = None
        self.default_config.update({
            '_enabled': True,
            'Pick Up White List': ['吸收', 'Absorb'],
            'Pick Up Black List': ['开始合成', '领取奖励', 'Claim', '合成台']
        })

    def send_fs(self):
        # if self.debug:
        #     self.screenshot('pick_up', show_box=True)
        self.send_key('f')
        self.sleep(0.2)
        self.send_key('f')
        self.sleep(0.2)
        self.send_key('f')
        self.sleep(0.2)

    def run(self):
        if not self.scene.in_team(self.in_team_and_world):
            return
        start = time.time()
        while time.time() - start < 1:
            f = self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box,
                              threshold=0.8)
            if not f:
                return
            percent = self.calculate_color_percentage(f_white_color, f)
            if percent < 0.5:
                self.log_debug(f'f white color percent: {percent} wait')
                self.next_frame()
                continue
            dialog_search = f.copy(x_offset=f.width * 3, width_offset=f.width * 2, height_offset=f.height * 2,
                                   y_offset=-f.height,
                                   name='search_dialog')

            text_area = dialog_search.copy(x_offset=dialog_search.width, width_offset=f.width * 6,
                                           height_offset=0,
                                           y_offset=0)
            dialog_3_dots = self.find_feature('dialog_3_dots', box=dialog_search,
                                              threshold=0.6)

            if dialog_3_dots:
                if self.config.get('Pick Up White List'):
                    texts = self.ocr(box=text_area, match=self.config.get('Pick Up White List'))
                    if texts:
                        logger.info(f'found Pick Up White List {texts}')
                        self.send_fs()
                        return True
            else:
                if self.config.get('Pick Up Black List'):
                    texts = self.ocr(box=text_area, match=self.config.get('Pick Up Black List'))
                    if texts:
                        logger.info(f'found Pick Up Black List: {texts}')
                        return False
                self.send_fs()
                return True
            self.next_frame()
