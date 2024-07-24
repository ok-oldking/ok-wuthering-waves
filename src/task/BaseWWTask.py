import re

from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.BaseTask import BaseTask

logger = get_logger(__name__)


class BaseWWTask(BaseTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.absorb_echo_exclude_text = re.compile(r'(领取奖励|Claim)')

    @property
    def f_search_box(self):
        f_search_box = self.get_box_by_name('pick_up_f')
        f_search_box = f_search_box.copy(x_offset=-f_search_box.width / 2,
                                         width_offset=f_search_box.width,
                                         height_offset=f_search_box.height * 9,
                                         y_offset=-f_search_box.height * 5,
                                         name='search_dialog')
        return f_search_box

    def find_f_with_text(self, exclude_text=None):
        f = self.find_one('pick_up_f', box=self.f_search_box, threshold=0.8)
        if f and exclude_text:
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 12, height_offset=1 * f.height,
                                     y_offset=-0.5 * f.height)
            text = self.ocr(box=search_text_box, match=exclude_text)
            logger.debug(f'found f with text {text}, exclude_text {exclude_text}')
            if len(text) > 0:
                return False
        return f
