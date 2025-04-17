import re
import time
from datetime import datetime, timedelta

import numpy as np

from ok import BaseTask, Logger, find_boxes_by_name, og, Box
from ok import CannotFindException
import cv2


logger = Logger.get_logger(__name__)
number_re = re.compile(r'^(\d+)$')
stamina_re = re.compile(r'^(\d+)/(\d+)$')
f_white_color = {
    'r': (235, 255),  # Red range
    'g': (235, 255),  # Green range
    'b': (235, 255)  # Blue range
}

class BaseWWTask(BaseTask):
    map_zoomed = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pick_echo_config = self.get_global_config('Pick Echo Config')
        self.monthly_card_config = self.get_global_config('Monthly Card Config')
        self.next_monthly_card_start = 0
        self._logged_in = False
        self.bosses_pos = {
            'Bell-Borne Geochelone': [0, 0, False],
            'Dreamless': [0, 2, True],
            'Jue': [0, 3, True],
            'Hecate': [0, 4, True],
            'Fleurdelys': [0, 5, True],
            'Tempest Mephis': [0, 6, False],
            'Inferno Rider': [1, 0, False],
            'Impermanence Heron': [1, 1, False],
            'Lampylumen Myriad': [1, 2, False],
            'Feilian Beringal': [1, 3, False],
            'Mourning Aix': [1, 4, False],
            'Crownless': [1, 5, False],
            'Mech Abomination': [1, 6, False],
            'Thundering Mephis': [2, 0, False],
            'Fallacy of No Return': [2, 1, False],
            'Lorelei': [2, 2, False],
            'Sentry Construct': [2, 3, False],
            'Dragon of Dirge': [2, 4, False],
            'Nightmare: Feilian Beringal': [2, 5, False],
            'Nightmare: Impermanence Heron': [2, 6, False],
            'Nightmare: Thundering Mephis': [3, 0, False],
            'Nightmare: Tempest Mephis': [3, 1, False],
            'Nightmare: Crownless': [3, 2, False],
            'Nightmare: Inferno Rider': [3, 3, False],
            'Nightmare: Mourning Aix': [3, 4, False],
            'Nightmare: Lampylumen Myriad': [3, 5, False],
        }

    def zoom_map(self):
        if not self.map_zoomed:
            self.log_info('zoom map to max')
            self.map_zoomed = True
            self.send_key('m', after_sleep=1)
            self.click_relative(0.94, 0.33, after_sleep=0.5)
            self.send_key('esc', after_sleep=1)

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
                                         width_offset=f_search_box.width * 0.65,
                                         height_offset=f_search_box.height * 6,
                                         y_offset=-f_search_box.height * 5,
                                         name='search_dialog')
        return f_search_box

    def find_f_with_text(self, target_text=None):
        f = self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box, threshold=0.8)
        if not f:
            return None
        if not target_text:
            return f

        start = time.time()
        percent = 0.0
        while time.time() - start < 1:
            percent = self.calculate_color_percentage(f_white_color, f)
            if percent > 0.5:
                break
            self.next_frame()
            self.log_debug(f'f white color percent: {percent} wait')
        if percent < 0.5:
            return None

        if target_text:
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 7, height_offset=1.5 * f.height,
                                     y_offset=-0.8 * f.height, name='search_text_box')
            text = self.ocr(box=search_text_box, match=target_text, target_height=540)
            logger.debug(f'found f with text {text}, target_text {target_text}')
            if not text:
                return None
        return f

    def walk_to_yolo_echo(self, time_out=15):
        last_direction = None
        start = time.time()
        no_echo_start = 0
        while time.time() - start < time_out:
            self.next_frame()
            if self.pick_f():
                self.log_debug('pick echo success')
                self._stop_last_direction(last_direction)
                return True
            echos = self.find_echos()
            if not echos:
                if no_echo_start == 0:
                    no_echo_start = time.time()
                elif time.time() - no_echo_start > 3:
                    self.log_debug(f'walk front to_echo, no echos found, break')
                    break
                next_direction = 'w'
            else:
                no_echo_start = 0
                echo = echos[0]
                center_distance = echo.center()[0] - self.width_of_screen(0.5)
                threshold = 0.05 if not last_direction else 0.15
                if abs(center_distance) < self.height_of_screen(threshold):
                    if echo.y + echo.height > self.height_of_screen(0.65):
                        next_direction = 's'
                    else:
                        next_direction = 'w'
                elif center_distance > 0:
                    next_direction = 'd'
                else:
                    next_direction = 'a'
            last_direction = self._walk_direction(last_direction, next_direction)
        self._stop_last_direction(last_direction)


    def _walk_direction(self, last_direction, next_direction):
        if next_direction != last_direction:
            self._stop_last_direction(last_direction)
            if next_direction:
                self.send_key_down(next_direction)
        return next_direction

    def _stop_last_direction(self, last_direction):
        if last_direction:
            self.send_key_up(last_direction)
            self.sleep(0.01)
        return None

    def walk_to_box(self, find_function, time_out=30, end_condition=None, y_offset=0.05):
        if not find_function:
            self.log_info('find_function not found, break')
            return False
        last_direction = None
        start = time.time()
        ended = False
        last_target = None
        while time.time() - start < time_out:
            self.next_frame()
            if end_condition:
                ended = end_condition()
                if ended:
                    break
            treasure_icon = find_function()
            if isinstance(treasure_icon, list):
                if len(treasure_icon) > 0:
                    treasure_icon = treasure_icon[0]
                else:
                    treasure_icon = None
            if treasure_icon:
                last_target = treasure_icon
            if last_target is None:
                next_direction = self.opposite_direction(last_direction)
                self.log_info('find_function not found, change to opposite direction')
            else:
                x, y = last_target.center()
                y = max(0, y - self.height_of_screen(y_offset))
                next_direction = self.get_direction(x, y, self.width, self.height, current_direction=last_direction)

            if next_direction != last_direction:
                if last_direction:
                    self.send_key_up(last_direction)
                    self.sleep(0.02)
                last_direction = next_direction
                if next_direction:
                    self.send_key_down(next_direction)
        if last_direction:
            self.send_key_up(last_direction)
            self.sleep(0.02)
        if not end_condition:
            return last_direction is not None
        else:
            return ended

    def opposite_direction(self, direction):
        if direction == 'w':
            return 's'
        elif direction == 's':
            return 'w'
        elif direction == 'a':
            return 'd'
        elif direction == 'd':
            return 'a'
        else:
            return 'w'

    def get_direction(self, location_x, location_y, screen_width, screen_height, current_direction):
        """
        Determines the direction ('w', 'a', 's', 'd') closest to the screen center.
        Args:
            location_x: The x-coordinate of the point.
            location_y: The y-coordinate of the point.
            screen_width: The width of the screen.
            screen_height: The height of the screen.
        Returns:
            A string "w", "a", "s", or "d".
        """
        if screen_width <= 0 or screen_height <= 0:
            # Handle invalid dimensions, default based on horizontal position
            return "a" if location_x < screen_width / 2 else "d"
        center_x = screen_width / 2
        center_y = screen_height / 2
        # Calculate vector from point towards the center
        delta_x = center_x - location_x
        delta_y = center_y - location_y
        # Determine dominant direction based on vector magnitude
        direction = None
        if (abs(delta_x) > abs(delta_y) or (not current_direction and abs(delta_x) > 0.05 * screen_height)
                or abs(delta_x) > 0.15 * screen_height):
            # More horizontal movement needed
            return "a" if delta_x > 0 else "d"

            # More vertical movement needed (or equal)
        return "w" if delta_y > 0 else "s"

    def find_treasure_icon(self):
        return self.find_one('treasure_icon', box=self.box_of_screen(0.1, 0.2, 0.9, 0.8), threshold=0.7)

    def click(self, x=-1, y=-1, move_back=False, name=None, interval=-1, move=True, down_time=0.01, after_sleep=0, key="left"):
        if x == -1 and y == -1:
            x = self.width_of_screen(0.5)
            y = self.height_of_screen(0.5)
            move = False
            down_time = 0.01
        else:
            down_time = 0.2
        return super().click(x, y, move_back, name, interval, move=move, down_time=down_time, after_sleep=after_sleep, key=key)

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

    def in_realm(self):
        illusive_realm_exit = self.find_one('illusive_realm_exit',
                                            use_gray_scale=False, threshold=0.5)
        return illusive_realm_exit is not None

    def walk_until_f(self, direction='w', time_out=0, raise_if_not_found=True, backward_time=0, target_text=None,
                     cancel=True):
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
            if cancel and self.handle_claim_button():
                return False
        self.sleep(0.5)
        return True

    def get_stamina(self):
        boxes = self.wait_ocr(0.49, 0.01, 0.92, 0.10, log=True, raise_if_not_found=False,
                              match=[number_re, stamina_re])
        if len(boxes) == 0:
            return -1, -1
        current_box = find_boxes_by_name(boxes, stamina_re)[0]
        current = int(current_box.name.split('/')[0])
        back_up_box = find_boxes_by_name(boxes, number_re)[0]
        back_up = int(back_up_box.name)
        self.info_set('current_stamina', current)
        self.info_set('back_up_stamina', back_up)
        return current, back_up

    def ensure_stamina(self, min_stamina, max_stamina):
        current, back_up = self.get_stamina()
        if current >= max_stamina:
            return max_stamina, current + back_up - max_stamina, current - max_stamina, False
        elif current + back_up >= max_stamina:
            self.add_stamina(max_stamina - current)
            return max_stamina, current + back_up - max_stamina, 0, True
        elif current >= min_stamina:
            return min_stamina, current + back_up - min_stamina, current - min_stamina, False
        elif current + back_up >= min_stamina:
            self.add_stamina(min_stamina - current)
            return min_stamina, current + back_up - min_stamina, 0, True

    def add_stamina(self, to_add):
        self.click(0.83, 0.05, after_sleep=1)
        self.wait_ocr(0.41, 0.47, 0.45, 0.54, match=number_re, raise_if_not_found=True)
        self.click(0.7, 0.7, after_sleep=1)
        back_up = int(
            self.wait_ocr(0.6, 0.53, 0.66, 0.62, match=number_re, raise_if_not_found=True)[0].name)
        to_minus = back_up - to_add
        self.log_info(f'add_stamina, to_minus:{to_minus}, to_add:{to_add}, back_up:{back_up}')
        for _ in range(to_minus):
            self.click(0.24, 0.58, after_sleep=0.01)
        self.click_relative(0.69, 0.71, after_sleep=2)
        self.info_set('add_stamina', to_add)
        self.back(after_sleep=1)
        self.back(after_sleep=1)

    def send_key_and_wait_f(self, direction, raise_if_not_found, time_out, running=False, target_text=None,
                            cancel=True):
        if time_out <= 0:
            return
        start = time.time()
        if running:
            self.mouse_down(key='right')
        self.send_key_down(direction)
        f_found = self.wait_until(lambda: self.find_f_with_text(target_text=target_text), time_out=time_out,
                                  raise_if_not_found=False)
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

        if cancel and self.handle_claim_button():
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
            self.sleep(0.5)
            logger.debug(f'run_until condiction {condiction} direction {direction}')
            self.mouse_down(key='right')
        self.sleep(1)
        result = self.wait_until(condiction, time_out=time_out,
                                 raise_if_not_found=raise_if_not_found)
        self.send_key_up(direction)
        if running:
            self.mouse_up(key='right')
        return result

    def is_moving(self):
        return False

    def handle_claim_button(self):
        if self.wait_feature('claim_cancel_button_hcenter_vcenter', raise_if_not_found=False, horizontal_variance=0.05,
                             vertical_variance=0.1, time_out=1.5, threshold=0.8):
            self.sleep(0.5)
            self.send_key('esc')
            self.sleep(0.5)
            logger.info(f"found a claim reward")
            return True

    def test_absorb(self):
        # self.set_image('tests/images/absorb.png')
        image = cv2.imread('tests/images/absorb.png')
        result = self.executor.ocr_lib(image, use_det=True, use_cls=False, use_rec=True)
        self.logger.info(f'ocr_result {result}')

    def find_echos(self, threshold=0.46):
        """
        Main function to load ONNX model, perform inference, draw bounding boxes, and display the output image.

        Args:
            onnx_model (str): Path to the ONNX model.
            input_image (ndarray): Path to the input image.

        Returns:
            list: List of dictionaries containing detection information such as class_id, class_name, confidence, etc.
        """
        # Load the ONNX model
        ret = og.my_app.yolo_detect(self.frame, threshold=threshold, label=0)

        for box in ret:
            box.y += box.height * 1/3
            box.height = 1
        self.draw_boxes("echo", ret)
        return ret

    def yolo_find_all(self, threshold=0.3):
        """
        Main function to load ONNX model, perform inference, draw bounding boxes, and display the output image.

        Args:
            onnx_model (str): Path to the ONNX model.
            input_image (ndarray): Path to the input image.

        Returns:
            list: List of dictionaries containing detection information such as class_id, class_name, confidence, etc.
        """
        # Load the ONNX model
        boxes = og.my_app.yolo_detect(self.frame, threshold=threshold, label=-1)
        ret = sorted(boxes, key=lambda detection: detection.confidence, reverse=True)
        return ret

    def pick_echo(self):
        if self.find_f_with_text(target_text=self.absorb_echo_text()):
            # if self.debug:
            #     self.screenshot('pick_echo')
            self.send_key('f')
            if not self.handle_claim_button():
                self.log_debug('found a echo picked')
                return True

    def pick_f(self):
        if self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box, threshold=0.8):
            self.send_key('f')
            if not self.handle_claim_button():
                self.log_debug('found a echo picked')
                return True

    def yolo_find_echo(self, use_color=False, turn=True):
        if self.debug:
            # self.draw_boxes('echo', echos)
            self.screenshot('yolo_echo_start')
        max_echo_count = 0
        if self.pick_echo():
            self.sleep(0.5)
            return True, True
        front_box = self.box_of_screen(0.35, 0.35, 0.65, 0.53, hcenter=True)
        color_threshold = 0.02
        for i in range(4):
            if turn:
                self.center_camera()
            echos = self.find_echos()
            max_echo_count = max(max_echo_count, len(echos))
            self.log_debug(f'max_echo_count {max_echo_count}')
            if echos:
                self.log_info(f'yolo found echo {echos}')
                # return self.walk_to_box(self.find_echos, time_out=15, end_condition=self.pick_echo), max_echo_count > 1
                return self.walk_to_yolo_echo(), max_echo_count > 1
            if use_color:
                color_percent = self.calculate_color_percentage(echo_color, front_box)
                self.log_debug(f'pick_echo color_percent:{color_percent}')
                if color_percent > color_threshold:
                    # if self.debug:
                    #     self.screenshot('echo_color_picked')
                    self.log_debug(f'found color_percent {color_percent} > {color_threshold}, walk now')
                    #return self.walk_to_box(self.find_echos, time_out=15, end_condition=self.pick_echo), max_echo_count > 1
                    return self.walk_to_yolo_echo(), max_echo_count > 1
            if not turn and i == 0:
                return False, max_echo_count > 1
            self.send_key('a', down_time=0.05)
            self.sleep(0.5)

        self.center_camera()
        return False, max_echo_count > 1

    def center_camera(self):
        self.click(0.5, 0.5, down_time=0.2, after_sleep=1, key='middle')

    def turn_direction(self, direction):
        if direction != 'w':
            self.send_key(direction, down_time=0.05, after_sleep=0.5)
        self.center_camera()

    def walk_find_echo(self, backward_time=1, time_out=4):
        if self.walk_until_f(time_out=time_out, backward_time=backward_time, target_text=self.absorb_echo_text(),
                             raise_if_not_found=False):  # find and pick echo
            logger.debug(f'farm echo found echo move forward walk_until_f to find echo')
            return True

    def incr_drop(self, dropped):
        if dropped:
            self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1
            self.info['Echo per Hour'] = round(self.info.get('Echo Count', 0) / max(time.time() - self.start_time, 1) * 3600)

    def should_check_monthly_card(self):
        if self.next_monthly_card_start > 0:
            if 0 < time.time() - self.next_monthly_card_start < 120:
                return True
        return False

    def sleep(self, timeout):
        return super().sleep(timeout - self.check_for_monthly_card())

    def wait_in_team_and_world(self, time_out=10, raise_if_not_found=True, esc=False):
        return self.wait_until(self.in_team_and_world, time_out=time_out, raise_if_not_found=raise_if_not_found,
                               post_action=lambda: self.back(after_sleep=2) if esc else None)

    def ensure_main(self, esc=True, time_out=30):
        self.info_set('current task', 'wait main')
        if not self.wait_until(lambda: self.is_main(esc=esc), time_out=time_out, raise_if_not_found=False):
            raise Exception('Please start in game world and in team!')
        self.info_set('current task', 'in main')

    def is_main(self, esc=True):
        if self.in_team_and_world():
            self._logged_in = True
            return True
        if self.handle_monthly_card():
            return True
        if self.wait_login():
            return True
        if esc:
            self.back(after_sleep=1.5)

    def wait_login(self):
        if not self._logged_in:
            if login := self.ocr(0.3, 0.3, 0.7, 0.7, match="登录"):
                self.click(login)
                self.log_info('点击登录按钮!')
                return False
            if self.find_one('login_account', threshold=0.7):
                self.wait_until(lambda: self.find_one('login_account', threshold=0.7) is None,
                                pre_action=lambda: self.click_relative(0.5, 0.9, after_sleep=3), time_out=30)
                self.wait_until(lambda: self.find_one('monthly_card', threshold=0.7) or self.in_team_and_world(),
                                pre_action=lambda: self.click_relative(0.5, 0.9, after_sleep=3), time_out=120)
                self.wait_until(lambda: self.in_team_and_world(),
                                post_action=lambda: self.click_relative(0.5, 0.9, after_sleep=3), time_out=5)
                self.log_info('Auto Login Success', notify=True)
                self._logged_in = True
                self.sleep(3)
                return True

    def in_team_and_world(self):
        return self.in_team()[
            0]  # and self.find_one(f'gray_book_button', threshold=0.7, canny_lower=50, canny_higher=150)

    def in_team(self):
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
            self._logged_in = True
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
            self.wait_until(self.in_team_and_world, time_out=10,
                            post_action=lambda: self.click_relative(0.50, 0.89, after_sleep=1))
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
        self.zoom_map()
        pos = self.bosses_pos.get(boss_name)
        page = pos[0]
        index = pos[1]
        in_dungeon = pos[2]
        self.log_info(f'teleport to {boss_name} index {index} in_dungeon {in_dungeon}')
        self.sleep(1)
        self.openF2Book()

        gray_book_boss = self.wait_book()

        self.log_info(f'click {gray_book_boss}')
        self.click_box(gray_book_boss)
        self.sleep(2)

        if page == 1:  # weekly turtle
            logger.info('scroll down page 1')
            self.click_relative(1136 / 2560, 455 / 2160)
            self.sleep(1)
        elif page == 2:
            logger.info('scroll down page 2')
            self.click_relative(1136 / 2560, 550 / 2160)
            self.sleep(1)
        elif page == 3:
            logger.info('scroll down page 3')
            self.click_relative(1136 / 2560, 640 / 2160)
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
        self.sleep(1)

    def openF2Book(self, feature="gray_book_all_monsters"):
        self.sleep(1)
        self.log_info('click f2 to open the book')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.77, 0.05)
        self.send_key_up('alt')
        # self.send_key('f2')
        gray_book_boss = self.wait_book(feature)
        if not gray_book_boss:
            self.log_error("can't find gray_book_boss, make sure f2 is the hotkey for book", notify=True)
            raise Exception("can't find gray_book_boss, make sure f2 is the hotkey for book")
        return gray_book_boss

    def click_traval_button(self):
        for feature_name in ['fast_travel_custom', 'gray_teleport', 'remove_custom']:
            if feature := self.find_one(feature_name, threshold=0.7):
                self.click(feature, after_sleep=1)
                if feature.name == 'fast_travel_custom':
                    if self.wait_click_feature(['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                                           relative_x=-1, raise_if_not_found=False,
                                           threshold=0.6,
                                           time_out=2):
                        self.wait_click_feature(['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                                            relative_x=-1, raise_if_not_found=False,
                                            threshold=0.6,
                                            time_out=1)
                return True

    def wait_click_travel(self):
        self.wait_until(self.click_traval_button, raise_if_not_found=True, time_out=10,
                        settle_time=1)

    def wait_book(self, feature="gray_book_all_monsters"):
        gray_book_boss = self.wait_until(
            lambda: self.find_one(feature, vertical_variance=0.8, horizontal_variance=0.05,
                                  threshold=0.3),
            time_out=3, settle_time=2)
        logger.info(f'found gray_book_boss {gray_book_boss}')
        # if self.debug:
        #     self.screenshot(feature)
        return gray_book_boss

    def check_main(self):
        if not self.in_team()[0]:
            self.click_relative(0, 0)
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
