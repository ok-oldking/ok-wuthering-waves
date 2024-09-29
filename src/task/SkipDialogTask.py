import time

import re
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TriggerTask import TriggerTask
from src.task.BaseWWTask import BaseWWTask

logger = get_logger(__name__)


class AutoDialogTask(TriggerTask, BaseWWTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.default_config = {'_enabled': True}
        self.skip = None
        self.trigger_interval = 1
        self.has_eye_time = 0
        self.name = "Skip Dialog during Quests"
        self.confirm_dialog_checked = False

    def run(self):
        pass

    def skip_confirm(self):
        if not self.confirm_dialog_checked:
            if self.calculate_color_percentage(dialog_white_color, box=self.box_of_screen(0.42, 0.59, 0.56,
                                                                                          0.64)) > 0.9 and self.calculate_color_percentage(
                dialog_black_color, box=self.box_of_screen(0.61, 0.60, 0.74, 0.64)) > 0.8:
                logger.info('confirm dialog exists, click confirm')
                self.click_relative(0.44, 0.55)
                self.sleep(0.2)
                self.click_relative(0.67, 0.62)
                self.confirm_dialog_checked = True
                return True
        if skip_button := self.find_one('skip_quest_confirm', threshold=0.8):
            self.click(skip_button)
            return True
        if self.in_team_and_world():
            return True

    def trigger(self):
        skip = self.ocr(0.03, 0.03, 0.11, 0.10, target_height=540, match=re.compile(r'SKIP', re.IGNORECASE),
                        threshold=0.7)
        if skip:
            logger.info('Click Skip Dialog')
            self.click_box(skip, move_back=True)
            return self.wait_until(self.skip_confirm, wait_until_before_delay=0, time_out=3, raise_if_not_found=False)
        if time.time() - self.has_eye_time < 2:
            btn_dialog_close = self.find_one('btn_dialog_close', use_gray_scale=True, threshold=0.8)
            if btn_dialog_close:
                self.click(btn_dialog_close, move_back=True)
                return
        btn_dialog_eye = self.find_one('btn_dialog_eye', use_gray_scale=True, threshold=0.8)
        if btn_dialog_eye:
            self.has_eye_time = time.time()
            btn_auto_play_dialog = self.find_one('btn_auto_play_dialog', use_gray_scale=True)
            if btn_auto_play_dialog:
                self.click_box(btn_auto_play_dialog, move_back=True)
                logger.info('toggle auto play')
                self.sleep(0.2)
            if arrow := self.find_feature('btn_dialog_arrow', x=0.59, y=0.33, to_x=0.75, to_y=0.75,
                                          use_gray_scale=True, threshold=0.7):
                self.click(arrow[-1])
                logger.info('choose arrow')
                self.sleep(0.2)
            elif dots := self.find_feature('btn_dialog_3dots', x=0.59, y=0.33, to_x=0.75, to_y=0.75,
                                           use_gray_scale=True, threshold=0.7):
                if dots:
                    self.click(dots[-1])
                    logger.info('choose dot')
                    self.sleep(0.2)
            return


dialog_white_color = {
    'r': (230, 255),  # Red range
    'g': (230, 255),  # Green range
    'b': (230, 255)  # Blue range
}

dialog_black_color = {
    'r': (0, 15),  # Red range
    'g': (0, 15),  # Green range
    'b': (0, 15)  # Blue range
}
