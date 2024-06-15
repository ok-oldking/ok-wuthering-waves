import re

from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TriggerTask import TriggerTask

logger = get_logger(__name__)


class AutoDialogTask(TriggerTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.skip = None
        self.confirm_dialog_checked = False
        self.check_trigger_interval = 0.2

    def run(self):
        pass

    def trigger(self):
        skip = self.ocr(0.03, 0.03, 0.11, 0.10, match=re.compile('SKIP'), threshold=0.9)
        if skip:
            logger.info('Click Skip Dialog')
            self.click_box(skip, move_back=True)
            if not self.confirm_dialog_checked:
                logger.info('Start checking if confirm dialog exists')
                self.sleep(2)
                if self.calculate_color_percentage(dialog_white_color, box=self.box_of_screen(0.42, 0.59, 0.56,
                                                                                              0.64)) > 0.9 and self.calculate_color_percentage(
                    dialog_black_color, box=self.box_of_screen(0.61, 0.60, 0.74, 0.64)) > 0.8:
                    logger.info('confirm dialog exists, click confirm')
                    self.click_relative(0.44, 0.55)
                    self.sleep(0.2)
                    self.click_relative(0.67, 0.62)
                else:
                    self.screenshot('dialog')
                    logger.info('confirm dialog does not exist')
                self.confirm_dialog_checked = True


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
