from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.BaseTask import BaseTask

logger = get_logger(__name__)


class BaseWWTask(BaseTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()

    @property
    def absorb_echo_feature(self):
        return self.get_feature_by_lang('absorb')

    def get_feature_by_lang(self, feature):
        lang_feature = feature + '_' + self.game_lang
        if self.feature_exists(lang_feature):
            return lang_feature
        else:
            return None

    @property
    def f_search_box(self):
        f_search_box = self.get_box_by_name('pick_up_f')
        f_search_box = f_search_box.copy(x_offset=-f_search_box.width / 2,
                                         width_offset=f_search_box.width,
                                         height_offset=f_search_box.height * 9,
                                         y_offset=-f_search_box.height * 5,
                                         name='search_dialog')
        return f_search_box

    def find_f_with_text(self, target_text=None):
        f = self.find_one('pick_up_f', box=self.f_search_box, threshold=0.8)
        if f and target_text:
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 12, height_offset=1 * f.height,
                                     y_offset=-0.5 * f.height)
            text = self.find_one(target_text, box=search_text_box, canny_lower=75, canny_higher=150, threshold=0.65)
            logger.debug(f'found f with text {text}, target_text {target_text}')
            if not text:
                return None
        return f

    @property
    def game_lang(self):
        if '鸣潮' in self.hwnd_title:
            return 'zh_CN'
        elif 'Wuthering' in self.hwnd_title:
            return 'en_US'
        return 'unknown_lang'
