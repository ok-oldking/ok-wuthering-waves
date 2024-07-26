import re
import time
from datetime import datetime, timedelta

from ok.config.ConfigOption import ConfigOption
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.BaseTask import BaseTask

logger = get_logger(__name__)

pick_echo_config_option = ConfigOption('Pick Echo Config', {
    'Use OCR': False
}, config_description={
    'Use OCR': 'Turn on if your CPU is Powerful for more accuracy'})

monthly_card_config_option = ConfigOption('Monthly Card Config', {
    'Check Monthly Card': False,
    'Monthly Card Time': 4
}, config_description={
    'Check Monthly Card': 'Check for monthly card to avoid interruption of tasks',
    'Monthly Card Time': 'Your computer\'s local time when the monthly card will popup, hour in (1-24)'
})


class BaseWWTask(BaseTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.pick_echo_config = self.get_config(pick_echo_config_option)
        self.monthly_card_config = self.get_config(monthly_card_config_option)
        self.next_monthly_card_start = 0

    def validate(self, key, value):
        message = self.validate_config(key, value)
        if message:
            return False, message
        else:
            return True, None

    @property
    def absorb_echo_text(self):
        if self.pick_echo_config.get('Use OCR') and (self.game_lang == 'zh_CN' or self.game_lang == 'en_US'):
            return re.compile(r'(吸收|Absorb)')
        else:
            return None

    @property
    def absorb_echo_feature(self):
        return self.get_feature_by_lang('absorb')

    def get_feature_by_lang(self, feature):
        lang_feature = feature + '_' + self.game_lang
        if self.feature_exists(lang_feature):
            return lang_feature
        else:
            return None

    def set_check_monthly_card(self):
        if self.monthly_card_config.get('Check Monthly Card'):
            now = datetime.now()
            hour = self.monthly_card_config.get('Monthly Card Time')
            # Calculate the next 4 o'clock in the morning
            next_four_am = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if now >= next_four_am:
                next_four_am += timedelta(days=1)
            next_monthly_card_start_date_time = next_four_am - timedelta(seconds=30)
            # Subtract 1 minute from the next 4 o'clock in the morning
            self.next_monthly_card_start = next_monthly_card_start_date_time.timestamp()
            logger.info('set next monthly card start time to {}'.format(next_monthly_card_start_date_time))
        else:
            self.next_monthly_card_start = 0

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
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 7, height_offset=1.5 * f.height,
                                     y_offset=-0.8 * f.height, name='search_text_box')
            text = self.ocr(box=search_text_box, match=target_text)
            logger.debug(f'found f with text {text}, target_text {target_text}')
            if not text:
                return None
        return f

    def check_for_monthly_card(self):
        if self.next_monthly_card_start > 0:
            if time.time() > self.next_monthly_card_start:
                start = time.time()
                logger.info(f'start waiting for monthly card')
                f4_open = False
                if self.in_team_and_world():
                    logger.info(f'in team send f4 to wait')
                    self.send_key('f4')
                    f4_open = True
                monthly_card = self.wait_until(self.handle_monthly_card, time_out=120, raise_if_not_found=False)
                logger.info(f'wait monthly card end {monthly_card}')
                if f4_open:
                    self.send_key('esc')
                    self.sleep(2)
                    logger.info(f'wait monthly card close f4')
                cost = time.time() - start
                self.set_check_monthly_card()
                return cost
        return 0

    def sleep(self, timeout):
        return super().sleep(timeout - self.check_for_monthly_card())

    def wait_in_team_and_world(self, time_out=10, raise_if_not_found=True):
        return self.wait_until(self.in_team_and_world, time_out=time_out, raise_if_not_found=raise_if_not_found)

    def in_team_and_world(self):
        return self.in_team()[
            0]  # and self.find_one(f'gray_book_button', threshold=0.7, canny_lower=50, canny_higher=150)

    def handle_monthly_card(self):
        monthly_card = self.find_one('monthly_card', threshold=0.8)
        if monthly_card is not None:
            self.click(monthly_card)
            self.sleep(2)
            self.click(monthly_card)
            self.sleep(1)
        logger.debug(f'check_monthly_card {monthly_card}')
        return monthly_card is not None

    @property
    def game_lang(self):
        if '鸣潮' in self.hwnd_title:
            return 'zh_CN'
        elif 'Wuthering' in self.hwnd_title:
            return 'en_US'
        return 'unknown_lang'
