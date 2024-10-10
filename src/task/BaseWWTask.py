import time

import re
from datetime import datetime, timedelta
from ok.config.ConfigOption import ConfigOption
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.BaseTask import BaseTask
from ok.task.TaskExecutor import CannotFindException

logger = get_logger(__name__)

pick_echo_config_option = ConfigOption('Pick Echo Config', {
    'Use OCR': False
}, config_description={
    'Use OCR': 'Turn on if your CPU is Powerful for more accuracy'}, description='Turn on to enable auto pick echo')

monthly_card_config_option = ConfigOption('Monthly Card Config', {
    'Check Monthly Card': False,
    'Monthly Card Time': 4
}, description='Turn on to avoid interruption by monthly card when executing tasks', config_description={
    'Check Monthly Card': 'Check for monthly card to avoid interruption of tasks',
    'Monthly Card Time': 'Your computer\'s local time when the monthly card will popup, hour in (1-24)'
})


class BaseWWTask(BaseTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.pick_echo_config = self.get_global_config(pick_echo_config_option)
        self.monthly_card_config = self.get_global_config(monthly_card_config_option)
        self.next_monthly_card_start = 0

        self.multiplayer_check_interval = 3
        self._in_multiplayer = False
        self._multiplayer_last_check = 0
        self.bosses_pos = {
            'Bell-Borne Geochelone': [0, 0, False],
            'Dreamless': [0, 2, True],
            'Jue': [0, 3, True],
            'Tempest Mephis': [0, 4, False],
            'Inferno Rider': [0, 5, False],
            'Impermanence Heron': [0, 6, False],
            'Lampylumen Myriad': [1, 0, False],
            'Feilian Beringal': [1, 1, False],
            'Mourning Aix': [1, 2, False],
            'Crownless': [1, 3, False],
            'Mech Abomination': [1, 4, False],
            'Thundering Mephis': [1, 5, False],
            'Fallacy of No Return': [1, 6, False],
        }

    def validate(self, key, value):
        message = self.validate_config(key, value)
        if message:
            return False, message
        else:
            return True, None

    def absorb_echo_text(self, ignore_config=False):
        if (self.pick_echo_config.get('Use OCR') or self.ocr_lib == 'paddleocr' or ignore_config) and (
                self.game_lang == 'zh_CN' or self.game_lang == 'en_US'):
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

    def set_check_monthly_card(self, next_day=False):
        if self.monthly_card_config.get('Check Monthly Card'):
            now = datetime.now()
            hour = self.monthly_card_config.get('Monthly Card Time')
            # Calculate the next 4 o'clock in the morning
            next_four_am = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if now >= next_four_am or next_day:
                next_four_am += timedelta(days=1)
            next_monthly_card_start_date_time = next_four_am - timedelta(seconds=30)
            # Subtract 1 minute from the next 4 o'clock in the morning
            self.next_monthly_card_start = next_monthly_card_start_date_time.timestamp()
            logger.info('set next monthly card start time to {}'.format(next_monthly_card_start_date_time))
        else:
            self.next_monthly_card_start = 0

    @property
    def f_search_box(self):
        f_search_box = self.get_box_by_name('pick_up_f_hcenter_vcenter')
        f_search_box = f_search_box.copy(x_offset=-f_search_box.width * 0.3,
                                         width_offset=f_search_box.width * 0.6,
                                         height_offset=f_search_box.height * 6,
                                         y_offset=-f_search_box.height * 5,
                                         name='search_dialog')
        return f_search_box

    def find_f_with_text(self, target_text=None):
        f = self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box, threshold=0.8)
        if f and target_text:
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 7, height_offset=1.5 * f.height,
                                     y_offset=-0.8 * f.height, name='search_text_box')
            text = self.ocr(box=search_text_box, match=target_text, target_height=540)
            logger.debug(f'found f with text {text}, target_text {target_text}')
            if not text:
                return None
        return f

    def click(self, x=-1, y=-1, move_back=False, name=None, interval=-1, move=True, down_time=0.01, after_sleep=0):
        if x == -1 and y == -1:
            x = self.width_of_screen(0.5)
            y = self.height_of_screen(0.5)
            move = False
            down_time = 0.01
        else:
            down_time = 0.16
        return super().click(x, y, move_back, name, interval, move=move, down_time=down_time, after_sleep=after_sleep)

    def check_for_monthly_card(self):
        if self.should_check_monthly_card():
            start = time.time()
            logger.info(f'check_for_monthly_card start check')
            if self.in_combat():
                logger.info(f'check_for_monthly_card in combat return')
                return time.time() - start
            if self.in_team_and_world():
                logger.info(f'check_for_monthly_card in team send sleep until monthly card popup')
                monthly_card = self.wait_until(self.handle_monthly_card, time_out=120, raise_if_not_found=False)
                logger.info(f'wait monthly card end {monthly_card}')
                cost = time.time() - start
                return cost
        return 0

    def walk_find_echo(self, backward_time=1):
        if self.walk_until_f(time_out=6, backward_time=backward_time, target_text=self.absorb_echo_text(),
                             raise_if_not_found=False):  # find and pick echo
            logger.debug(f'farm echo found echo move forward walk_until_f to find echo')
            return True

    def walk_until_f(self, direction='w', time_out=0, raise_if_not_found=True, backward_time=0, target_text=None):
        logger.info(f'walk_until_f direction {direction} target_text: {target_text}')
        if not self.find_f_with_text(target_text=target_text):
            if backward_time > 0:
                if self.send_key_and_wait_f('s', raise_if_not_found, backward_time, target_text=target_text):
                    logger.info('walk backward found f')
                    return True
            return self.send_key_and_wait_f(direction, raise_if_not_found, time_out,
                                            target_text=target_text) and self.sleep(0.5)
        else:
            self.send_key('f')
            if self.handle_claim_button():
                return False
        self.sleep(0.5)
        return True

    def send_key_and_wait_f(self, direction, raise_if_not_found, time_out, running=False, target_text=None):
        if time_out <= 0:
            return
        start = time.time()
        if running:
            self.mouse_down(key='right')
        self.send_key_down(direction)
        f_found = self.wait_until(lambda: self.find_f_with_text(target_text=target_text), time_out=time_out,
                                  raise_if_not_found=False, wait_until_before_delay=0)
        if f_found:
            self.send_key('f')
            self.sleep(0.1)
        self.send_key_up(direction)
        if running:
            self.mouse_up(key='right')
        if not f_found:
            if raise_if_not_found:
                raise CannotFindException('cant find the f to enter')
            else:
                logger.warning(f"can't find the f to enter")
                return False

        remaining = time.time() - start

        if self.handle_claim_button():
            self.sleep(0.5)
            self.send_key_down(direction)
            if running:
                self.mouse_down(key='right')
            self.sleep(remaining + 0.2)
            if running:
                self.mouse_up(key='right')
            self.send_key_up(direction)
            return False
        return f_found

    def run_until(self, condiction, direction, time_out, raise_if_not_found=False, running=False):
        if time_out <= 0:
            return
        self.send_key_down(direction)
        if running:
            self.mouse_down(key='right')
        result = self.wait_until(condiction, time_out=time_out,
                                 raise_if_not_found=raise_if_not_found, wait_until_before_delay=0)
        self.send_key_up(direction)
        if running:
            self.mouse_up(key='right')
        return result

    def is_moving(self):
        return False

    def handle_claim_button(self):
        if self.wait_feature('claim_cancel_button_hcenter_vcenter', raise_if_not_found=False, horizontal_variance=0.05,
                             vertical_variance=0.1, time_out=1.5, threshold=0.8, wait_until_before_delay=0.8):
            self.sleep(0.5)
            self.send_key('esc')
            self.sleep(0.5)
            logger.info(f"found a claim reward")
            return True

    def turn_and_find_echo(self):
        if self.walk_until_f(target_text=self.absorb_echo_text(), raise_if_not_found=False):
            return True
        box = self.box_of_screen(0.25, 0.20, 0.75, 0.53, hcenter=True)
        highest_percent = 0
        highest_index = 0
        threshold = 0.02
        for i in range(4):
            self.middle_click_relative(0.5, 0.5, down_time=0.2)
            self.sleep(1)
            color_percent = self.calculate_color_percentage(echo_color, box)
            if color_percent > highest_percent:
                highest_percent = color_percent
                highest_index = i
                if color_percent > threshold:
                    self.log_debug(f'found color_percent {color_percent} > {threshold}, walk now')
                    return self.walk_find_echo(backward_time=0.5)
            if self.debug:
                self.screenshot(f'find_echo_{highest_index}_{float(color_percent):.3f}_{float(highest_percent):.3f}')
            logger.debug(f'searching for echo {i} {float(color_percent):.3f} {float(highest_percent):.3f}')
            # self.click_relative(0.25, 0.25)
            self.send_key('a', down_time=0.05)
            self.sleep(0.5)

        if highest_percent > 0.0001:
            for i in range((highest_index + 1) % 4):
                self.middle_click_relative(0.5, 0.5)
                self.sleep(0.5)
                self.send_key('a', down_time=0.05)
                self.sleep(0.5)
            if self.debug:
                self.screenshot(f'pick_echo_{highest_index}')
            logger.info(f'found echo {highest_index} walk')
            return self.walk_find_echo(backward_time=0)

    def incr_drop(self, dropped):
        if dropped:
            self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1

    def should_check_monthly_card(self):
        if self.next_monthly_card_start > 0:
            if 0 < time.time() - self.next_monthly_card_start < 120:
                return True
        return False

    def sleep(self, timeout):
        return super().sleep(timeout - self.check_for_monthly_card())

    def wait_in_team_and_world(self, time_out=10, raise_if_not_found=True):
        return self.wait_until(self.in_team_and_world, time_out=time_out, raise_if_not_found=raise_if_not_found,
                               wait_until_before_delay=0)

    def in_team_and_world(self):
        return self.in_team()[
            0]  # and self.find_one(f'gray_book_button', threshold=0.7, canny_lower=50, canny_higher=150)

    def check_in_multiplayer(self):
        self._multiplayer_last_check = time.time()
        self._in_multiplayer = self.find_one('multiplayer_world_mark',
                                             threshold=0.75) is not None
        return self._in_multiplayer

    def in_multiplayer(self):
        if self._in_multiplayer or self._multiplayer_last_check == 0:
            return self.check_in_multiplayer()
        if not self._in_multiplayer and time.time() - self._multiplayer_last_check > self.multiplayer_check_interval:
            return self.check_in_multiplayer()
        return self._in_multiplayer

    def in_team(self):
        if self.in_multiplayer():
            return False, -1, -1
        c1 = self.find_one('char_1_text',
                           threshold=0.75)
        c2 = self.find_one('char_2_text',
                           threshold=0.75)
        c3 = self.find_one('char_3_text',
                           threshold=0.75)
        arr = [c1, c2, c3]
        # logger.debug(f'in_team check {arr} time: {(time.time() - start):.3f}s')
        current = -1
        exist_count = 0
        for i in range(len(arr)):
            if arr[i] is None:
                if current == -1:
                    current = i
            else:
                exist_count += 1
        if exist_count == 2 or exist_count == 1:
            return True, current, exist_count + 1
        else:
            return False, -1, exist_count + 1

        # Function to check if a component forms a ring

    def handle_monthly_card(self):
        monthly_card = self.find_one('monthly_card', threshold=0.8)
        # self.screenshot('monthly_card1')
        if monthly_card is not None:
            # self.screenshot('monthly_card1')
            self.click_relative(0.50, 0.89)
            self.sleep(2)
            # self.screenshot('monthly_card2')
            self.click_relative(0.50, 0.89)
            self.sleep(2)
            self.wait_until(self.in_team_and_world, time_out=10, post_action=lambda: self.click_relative(0.50, 0.89),
                            wait_until_before_delay=1)
            # self.screenshot('monthly_card3')
            self.set_check_monthly_card(next_day=True)
        logger.debug(f'check_monthly_card {monthly_card}')
        return monthly_card is not None

    @property
    def game_lang(self):
        if '鸣潮' in self.hwnd_title:
            return 'zh_CN'
        elif 'Wuthering' in self.hwnd_title:
            return 'en_US'
        return 'unknown_lang'

    def teleport_to_boss(self, boss_name):
        pos = self.bosses_pos.get(boss_name)
        page = pos[0]
        index = pos[1]
        in_dungeon = pos[2]
        self.log_info(f'teleport to {boss_name} index {index} in_dungeon {in_dungeon}')
        self.sleep(1)
        self.log_info('click f2 to open the book')
        self.send_key('f2')
        gray_book_boss = self.wait_book()
        if not gray_book_boss:
            self.log_error("can't find gray_book_boss, make sure f2 is the hotkey for book", notify=True)
            raise Exception("can't find gray_book_boss, make sure f2 is the hotkey for book")

        self.log_info(f'click {gray_book_boss}')
        self.click_box(gray_book_boss)
        self.sleep(2)

        if page == 1:  # weekly turtle
            logger.info('scroll down a page')
            self.click_relative(1136 / 2560, 0.27)
            self.sleep(1)

        x = 0.24
        y = 0.17
        step = (0.75 - y) / 6

        self.click_relative(x, y + step * index)
        self.sleep(1)
        self.log_info(f'index after scrolling down {index}')
        self.click_relative(0.89, 0.91)
        self.sleep(1)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=120)

    def click_traval_button(self):
        if self.find_one(['fast_travel_custom', 'remove_custom'], threshold=0.6):
            self.click_relative(0.91, 0.92, after_sleep=1)
            if self.wait_click_feature(['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                                       relative_x=-1, raise_if_not_found=True,
                                       threshold=0.7,
                                       time_out=5):
                self.wait_click_feature(['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                                        relative_x=-1, raise_if_not_found=False,
                                        threshold=0.7,
                                        time_out=1)
                return True
        elif btn := self.find_one('gray_teleport', threshold=0.7):
            return self.click_box(btn, relative_x=1)

    def wait_click_travel(self):
        self.wait_until(self.click_traval_button, raise_if_not_found=True, time_out=10)

    def wait_book(self):
        gray_book_boss = self.wait_until(
            lambda: self.find_one('gray_book_all_monsters', vertical_variance=0.8, horizontal_variance=0.05,
                                  threshold=0.4),
            time_out=3, wait_until_before_delay=2)
        logger.info(f'found gray_book_boss {gray_book_boss}')
        return gray_book_boss

    def check_main(self):
        if not self.in_team()[0]:
            self.send_key('esc')
            self.sleep(1)
            if not self.in_team()[0]:
                raise Exception('must be in game world and in teams')
        return True


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
