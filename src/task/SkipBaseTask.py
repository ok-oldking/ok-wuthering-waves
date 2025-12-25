import re
import time

from ok import Logger

from src.task.BaseWWTask import BaseWWTask, convert_bw, convert_dialog_icon

logger = Logger.get_logger(__name__)


class SkipBaseTask(BaseWWTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.confirm_dialog_checked = False
        self.has_eye_time = 0

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
        if skip_button := self.find_one('skip_quest_confirm_new', threshold=0.8):
            self.click(skip_button)
            return True
        if self.in_team_and_world():
            return True

    def find_skip(self):
        return self.find_one('skip_dialog', horizontal_variance=0.02, threshold=0.75,
                             frame_processor=convert_dialog_icon) or self.find_one('skip_dialog_new',
                                                                                   horizontal_variance=0.02,
                                                                                   threshold=0.75,
                                                                                   frame_processor=convert_dialog_icon)

    def try_click_skip(self):
        skipped = False
        while skip := self.find_skip():
            logger.info('Click Skip Dialog')
            self.click_box(skip, after_sleep=0.4)
            skipped = True
        return skipped

    def check_skip(self):
        if self.try_click_skip():
            return self.wait_until(self.skip_confirm, time_out=3, raise_if_not_found=False)
        if time.time() - self.has_eye_time < 2:
            btn_dialog_close = self.find_one('btn_dialog_close', threshold=0.8)
            if btn_dialog_close:
                self.click(btn_dialog_close, move_back=True)
                return True
        btn_dialog_eye = self.find_one('btn_dialog_eye', threshold=0.8)
        if btn_dialog_eye:
            self.has_eye_time = time.time()
            btn_auto_play_dialog = self.find_one('btn_auto_play_dialog')
            if btn_auto_play_dialog:
                self.click_box(btn_auto_play_dialog, move_back=True)
                logger.info('toggle auto play')
                self.sleep(0.2)
            if arrow := self.find_feature('btn_dialog_arrow', x=0.59, y=0.33, to_x=0.75, to_y=0.75,
                                          threshold=0.7):
                self.click(arrow[-1])
                logger.info('choose arrow')
                self.sleep(0.2)
            elif dots := self.find_feature('btn_dialog_3dots', x=0.59, y=0.33, to_x=0.75, to_y=0.75,
                                           threshold=0.7):
                if dots:
                    self.sleep(0.2)
                    if not self.try_click_skip():
                        self.click(dots[0])
                        logger.info('choose dot')
                        self.sleep(0.2)
            return True


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
