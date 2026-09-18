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
        if self.click_skip_dialog_confirm():
            self.confirm_dialog_checked = True
            return True
        if skip_button := self.find_one('skip_quest_confirm', threshold=0.8):
            # sleep 0.2 to stable click skip button
            self.sleep(0.2)
            self.click(skip_button)
            return True
        if skip_button := self.find_one('skip_quest_confirm_new', threshold=0.8):
            self.sleep(0.2)
            self.click(skip_button)
            return True
        if self.in_team_and_world():
            return True

    def find_skip(self):
        return self.find_one('skip_dialog', horizontal_variance=0.02, threshold=0.75,
                             frame_processor=convert_dialog_icon) or self.find_one('skip_dialog_new',
                                                                                   threshold=0.75,
                                                                                   frame_processor=convert_dialog_icon)

    def try_click_skip(self):
        skipped = False
        while skip := self.find_skip():
            logger.info('Click Skip Dialog')
            self.click_box(skip, after_sleep=0.2)
            skipped = True
        return skipped

    def check_skip(self):
        if self.try_click_skip():
            return self.wait_until(self.skip_confirm, time_out=3, raise_if_not_found=False)


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
