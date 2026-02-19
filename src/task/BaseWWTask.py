import math
import re
import time
from datetime import datetime, timedelta

import numpy as np

from ok import BaseTask, Logger, find_boxes_by_name, og, find_color_rectangles, mask_white
from ok import CannotFindException
import cv2

logger = Logger.get_logger(__name__)
number_re = re.compile(r'(\d+)')
stamina_re = re.compile(r'(\d+)/(\d+)')
f_white_color = {
    'r': (235, 255),  # Red range
    'g': (235, 255),  # Green range
    'b': (235, 255)  # Blue range
}
processed_feature = False


class BaseWWTask(BaseTask):
    map_zoomed = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pick_echo_config = self.get_global_config('Pick Echo Config')
        self.monthly_card_config = self.get_global_config('Monthly Card Config')
        self.char_config = self.get_global_config('Character Config')
        self.key_config = self.get_global_config('Game Hotkey Config')  # 游戏热键配置
        self.next_monthly_card_start = 0
        self._logged_in = False

    def is_open_world_auto_combat(self):
        from src.task.AutoCombatTask import AutoCombatTask
        from src.task.TacetTask import TacetTask
        from src.task.DailyTask import DailyTask
        if isinstance(self, AutoCombatTask):
            if not self.in_realm():
                return True
        elif isinstance(self, (TacetTask, DailyTask)):
            return True
        return False

    def zoom_map(self, esc=True):
        if not self.map_zoomed:
            self.log_info('zoom map to max')
            self.map_zoomed = True
            self.send_key('m', after_sleep=1)
            self.click_relative(0.94, 0.33, after_sleep=0.5)
            if esc:
                self.send_key('esc', after_sleep=1)

    def validate(self, key, value):
        message = self.validate_config(key, value)
        if message:
            return False, message
        else:
            return True, None

    def absorb_echo_text(self, ignore_config=False):
        if self.game_lang == 'zh_CN' or self.game_lang == 'en_US' or self.game_lang == 'zh_TW':
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
                                         height_offset=f_search_box.height * 6.5,
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
            search_text_box = f.copy(x_offset=f.width * 5, width_offset=f.width * 7, height_offset=4.5 * f.height,
                                     y_offset=-0.8 * f.height, name='search_text_box')
            text = self.ocr(box=search_text_box, match=target_text)
            logger.debug(f'found f with text {text}, target_text {target_text}')
            if text:
                if text[0].y > search_text_box.y + f.height * 1:
                    logger.debug(f'found f with text {text} below, target_text {target_text}')
                    self.scroll_relative(0.5, 0.5, 1)
                return f
        else:
            return f

    def has_target(self):
        return False

    def walk_to_yolo_echo(self, time_out=8, update_function=None, echo_threshold=0.5):
        last_direction = None
        start = time.time()
        no_echo_start = 0
        while time.time() - start < time_out:
            self.next_frame()
            if self.pick_f():
                self.log_debug('pick echo success')
                self._stop_last_direction(last_direction)
                return True
            if self.in_combat():
                self.log_debug('pick echo has_target return fail')
                self._stop_last_direction(last_direction)
                return False
            echos = self.find_echos(threshold=echo_threshold)
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
            if update_function is not None:
                update_function()
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

    def walk_to_box(self, find_function, time_out=30, end_condition=None, y_offset=0.05, x_threshold=0.07,
                    use_hook=False):
        start = time.time()
        while time.time() - start < time_out:
            if ended := self.do_walk_to_box(find_function, time_out=time_out - (time.time() - start),
                                            end_condition=end_condition, y_offset=y_offset,
                                            x_threshold=x_threshold, use_hook=use_hook):
                return ended

    def do_walk_to_box(self, find_function, time_out=30, end_condition=None, y_offset=0.05, x_threshold=0.07,
                       use_hook=False):
        if find_function:
            self.wait_until(lambda: (not end_condition or end_condition()) or find_function(), raise_if_not_found=True,
                            time_out=time_out)
        last_direction = None
        start = time.time()
        ended = False
        running = False
        last_target = None
        centered = False
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
                x_abs = abs(x - self.width_of_screen(0.5))
                threshold = 0.04 if not last_direction else x_threshold
                centered = centered or x_abs <= self.width_of_screen(threshold)
                if not centered:
                    if x > self.width_of_screen(0.5):
                        next_direction = 'd'
                    else:
                        next_direction = 'a'
                else:
                    if last_direction == 's':
                        center = 0.45
                    elif last_direction == 'w':
                        center = 0.6
                    else:
                        center = 0.5
                    if y > self.height_of_screen(center):
                        next_direction = 's'
                    else:
                        next_direction = 'w'
            if next_direction != last_direction:
                if last_direction:
                    self.send_key_up(last_direction)
                    self.sleep(0.001)
                last_direction = next_direction
                if next_direction:
                    self.send_key_down(next_direction)
            if running:
                if not self.find_one('on_the_wall', threshold=0.7):
                    self.log_info('not on the wall, stop running')
                    self.mouse_up(key='right')
            else:
                if next_direction == 'w' and self.find_one('on_the_wall', threshold=0.7):
                    self.log_info('on the wall, start running')
                    running = True
                    self.mouse_down(key='right')
                    self.sleep(0.1)
            if use_hook and next_direction == 'w':
                if self.find_one('tool_teleport', 0.75):
                    self.send_key(self.key_config['Tool Key'])
                    self.sleep(3)
                    continue
        if last_direction:
            self.send_key_up(last_direction)
            self.sleep(0.001)
        if running:
            self.send_key_up(self.key_config.get('Dodge Key'))
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

    def get_direction(self, location_x, location_y, screen_width, screen_height, centered, current_direction):
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
        return self.find_one('treasure_icon', box=self.box_of_screen(0.18, 0.1, 0.82, 0.81), threshold=0.7)

    def click(self, x=-1, y=-1, move_back=False, name=None, interval=-1, move=True, down_time=0.01, after_sleep=0,
              key="left"):
        if x == -1 and y == -1:
            x = self.width_of_screen(0.5)
            y = self.height_of_screen(0.5)
            move = False
            down_time = 0.01
        else:
            down_time = 0.2
        return super().click(x, y, move_back, name, interval, move=move, down_time=down_time, after_sleep=after_sleep,
                             key=key)

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
        return not bool(getattr(self, 'treat_as_not_in_realm', False)) and self.find_one('illusive_realm_exit',
                                                                                         threshold=0.7,
                                                                                         frame_processor=convert_bw) and self.in_team() and not self.find_one(
            'world_earth_icon', threshold=0.55,
            frame_processor=convert_bw)

    def in_world(self):
        return self.find_one('world_earth_icon', threshold=0.55,
                             frame_processor=convert_bw) and self.in_team() and not self.find_one('illusive_realm_exit',
                                                                                                  threshold=0.7,
                                                                                                  frame_processor=convert_bw)

    def in_illusive_realm(self):
        return self.find_one('new_realm_4') and self.in_realm() and self.find_one('illusive_realm_menu', threshold=0.6)

    def walk_until_f(self, direction='w', time_out=1, raise_if_not_found=True, backward_time=0, target_text=None,
                     check_combat=False, running=False):
        logger.info(f'walk_until_f direction {direction} target_text: {target_text}')
        if not self.find_f_with_text(target_text=target_text):
            # 视角朝前
            self.middle_click(after_sleep=0.2)
            if backward_time > 0:
                if self.send_key_and_wait_f('s', raise_if_not_found, backward_time, target_text=target_text,
                                            running=running, check_combat=check_combat):
                    logger.info('walk backward found f')
                    return True
            if self.send_key_and_wait_f(direction, raise_if_not_found, time_out, target_text=target_text,
                                        running=running, check_combat=check_combat):
                logger.info('walk forward found f')
                return True
            return False
        else:
            return True

    def get_stamina(self):
        boxes = self.wait_ocr(0.49, 0.0, 0.92, 0.10, raise_if_not_found=False,
                              match=[number_re, stamina_re])
        if not boxes:
            self.screenshot('stamina_error')
            return -1, -1, -1
        current = 0
        back_up = 0
        for box in boxes:
            if match := stamina_re.search(box.name):
                current = int(match.group(1))
            elif match := number_re.search(box.name):
                back_up = int(match.group(1))
        self.info_set('current_stamina', current)
        self.info_set('back_up_stamina', back_up)
        return current, back_up, current + back_up

    def use_stamina(self, once, must_use=0):
        self.sleep(1)
        current, back_up, total = self.get_stamina()
        y = 0.62
        if current >= once * 2:
            used = once * 2
            x = 0.67
            logger.info(f"当前体力大于等于双倍, {current} >= {once * 2}")
        elif must_use > once and total >= once * 2:
            used = once * 2
            x = 0.67
            logger.info(f"当前加备用大于日常剩余所需, 使用双倍, {must_use} >= {once} and {total} >= {once * 2}")
        else:
            used = once
            x = 0.32
            logger.info(f"使用单倍体力")
        self.click(x, y, after_sleep=0.5)
        if self.wait_feature('gem_add_stamina', horizontal_variance=0.4, vertical_variance=0.05,
                             time_out=1):  # 看是否需要使用备用体力
            self.click(0.70, 0.71, after_sleep=0.5)  # 点击确认
            self.click(0.70, 0.71, after_sleep=1)
            self.back(after_sleep=0.5)
            self.click(x, y, after_sleep=0.5)

        current -= used
        must_use -= used
        total -= used
        if total < once:
            logger.info(f"current stamina: {current} not enough to continue")
            can_continue = False
        elif must_use <= 0 and current < once:
            can_continue = False
            logger.info(f"current stamina: {current} must_use completed, no need to use back_up")
        else:
            can_continue = True
        return can_continue, used

    def send_key_and_wait_f(self, direction, raise_if_not_found, time_out, running=False, target_text=None,
                            check_combat=False):
        if time_out <= 0:
            return
        self.send_key_down(direction)
        if running:
            self.sleep(0.1)
            self.mouse_down(key='right')
        f_found = self.wait_until(
            lambda: self.find_f_with_text(target_text=target_text) or (check_combat and self.in_combat()),
            time_out=time_out,
            raise_if_not_found=False)
        self.send_key_up(direction)
        if running:
            self.sleep(0.1)
            self.mouse_up(key='right')
        if not f_found:
            if raise_if_not_found:
                raise CannotFindException('cant find the f to enter')
            else:
                logger.warning(f"can't find the f to enter")
                return False
        return f_found

    def run_until(self, condiction, direction, time_out, raise_if_not_found=False, running=False, target=False):
        if time_out <= 0:
            return
        self.send_key_down(direction)
        if running:
            self.sleep(0.1)
            logger.debug(f'run_until condiction {condiction} direction {direction}')
            self.mouse_down(key='right')
        start = time.time()
        result = None
        while time.time() - start < time_out:
            if result := condiction():
                break
            if target:
                self.middle_click(interval=0.5)
            self.sleep(0.02)
        self.send_key_up(direction)
        if running:
            self.sleep(0.1)
            self.mouse_up(key='right')

        if raise_if_not_found and not result:
            raise Exception('wait condition failed while walking')
        return result

    def is_moving(self):
        return False

    def handle_claim_button(self):
        while self.wait_until(self.has_claim, raise_if_not_found=False, time_out=1.5):
            self.sleep(0.5)
            self.send_key('esc')
            self.sleep(0.5)
            logger.info(f"handle_claim_button found a claim reward")
            return True

    def handle_claim_button_now(self):
        if self.has_claim():
            self.sleep(0.5)
            self.send_key('esc')
            self.sleep(0.2)
            logger.info(f"handle_claim_button_now found a claim reward")
            return True

    def has_claim(self):
        return not self.in_team()[0] and self.find_one('claim_cancel_button_hcenter_vcenter', horizontal_variance=0.05,
                                                       vertical_variance=0.1, threshold=0.8)

    def test_absorb(self):
        # self.set_image('tests/images/absorb.png')
        image = cv2.imread('tests/images/absorb.png')
        result = self.executor.ocr_lib(image, use_det=True, use_cls=False, use_rec=True)
        self.logger.info(f'ocr_result {result}')

    def find_echos(self, threshold=0.3):
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
            box.y += box.height * 1 / 3
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
            self.send_key('f')
            if not self.handle_claim_button():
                self.log_debug('found a echo picked')
                return True

    def pick_f(self, handle_claim=True):
        if self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box, threshold=0.8):
            self.send_key('f', after_sleep=0.8)
            if not handle_claim:
                return True
            if not self.handle_claim_button():
                self.log_debug('found a echo picked')
                return True

    def is_pick_f(self):
        f = self.find_one('pick_up_f_hcenter_vcenter', box=self.f_search_box,
                          threshold=0.8)
        if not f:
            return False
        dialog_search = f.copy(x_offset=f.width * 3, width_offset=f.width * 2, height_offset=f.height * 2,
                               y_offset=-f.height,
                               name='search_dialog')
        dialog_3_dots = self.find_feature('dialog_3_dots', box=dialog_search,
                                          threshold=0.6)
        return bool(dialog_3_dots)

    def walk_to_treasure(self, send_f=True, raise_if_not_found=True):
        if not self.walk_to_box(self.find_treasure_icon, end_condition=self.find_f_with_text):
            raise Exception(f'can not walk to treasure!')
        if send_f:
            self.walk_until_f(time_out=2, backward_time=0, raise_if_not_found=raise_if_not_found)
        self.sleep(1)

    def yolo_find_echo(self, use_color=False, turn=True, update_function=None, time_out=8, threshold=0.5):
        max_echo_count = 0
        if self.pick_echo():
            self.sleep(0.5)
            return True, True
        front_box = self.box_of_screen(0.35, 0.35, 0.65, 0.53, hcenter=True)
        color_threshold = 0.02
        for i in range(4):
            if turn:
                self.center_camera()
            echos = self.find_echos(threshold=threshold)
            max_echo_count = max(max_echo_count, len(echos))
            self.log_debug(f'max_echo_count {max_echo_count}')
            if echos:
                self.log_info(f'yolo found echo {echos}')
                # return self.walk_to_box(self.find_echos, time_out=15, end_condition=self.pick_echo), max_echo_count > 1
                return self.walk_to_yolo_echo(update_function=update_function, time_out=time_out), max_echo_count > 1
            if use_color:
                color_percent = self.calculate_color_percentage(echo_color, front_box)
                self.log_debug(f'pick_echo color_percent:{color_percent}')
                if color_percent > color_threshold:
                    # if self.debug:
                    #     self.screenshot('echo_color_picked')
                    self.log_debug(f'found color_percent {color_percent} > {color_threshold}, walk now')
                    # return self.walk_to_box(self.find_echos, time_out=15, end_condition=self.pick_echo), max_echo_count > 1
                    return self.walk_to_yolo_echo(update_function=update_function), max_echo_count > 1
            if not turn and i == 0:
                return False, max_echo_count > 1
            self.send_key('a', down_time=0.05)
            self.sleep(0.5)

        self.center_camera()
        return False, max_echo_count > 1

    def center_camera(self):
        self.click(0.5, 0.5, down_time=0.2, key='middle')
        self.wait_until(self.in_combat, time_out=1)

    def turn_direction(self, direction):
        if direction != 'w':
            self.send_key(direction, down_time=0.05, after_sleep=0.5)
        self.center_camera()

    def walk_find_echo(self, backward_time=1, time_out=3):
        if self.walk_until_f(time_out=time_out, backward_time=backward_time, target_text=self.absorb_echo_text(),
                             raise_if_not_found=False, check_combat=True):  # find and pick echo
            logger.debug(f'farm echo found echo move forward walk_until_f to find echo')
            return self.pick_f()

    def incr_drop(self, dropped):
        if dropped:
            self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1
            self.info['Echo per Hour'] = round(
                self.info.get('Echo Count', 0) / max(time.time() - self.start_time, 1) * 3600)

    def should_check_monthly_card(self):
        if self.next_monthly_card_start > 0:
            if 0 < time.time() - self.next_monthly_card_start < 120:
                return True
        return False

    def sleep(self, timeout):
        return super().sleep(timeout - self.check_for_monthly_card())

    def wait_in_team_and_world(self, time_out=10, raise_if_not_found=True, esc=False):
        success = self.wait_until(self.in_team_and_world, time_out=time_out, raise_if_not_found=raise_if_not_found,
                                  post_action=lambda: self.back(after_sleep=2) if esc else None)
        if success:
            self.sleep(0.1)
        return success

    def ensure_main(self, esc=True, time_out=30):
        self.info_set('current task', f'wait main esc={esc}')
        if not self.wait_until(lambda: self.is_main(esc=esc), time_out=time_out, raise_if_not_found=False):
            raise Exception('Please start in game world and in team!')
        self.sleep(0.5)
        self.info_set('current task', f'in main esc={esc}')

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
            if self.find_one('login_account', vertical_variance=0.1, threshold=0.7):
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
            texts = self.ocr()
            if login := self.find_boxes(texts, boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.7), match="登录"):
                if not self.find_boxes(texts, match="+86"):
                    self.click(login)
                    self.log_info('点击登录按钮!')
                return False
            if self.find_boxes(texts, match=re.compile("游戏即将重启")):
                self.log_info('游戏更新成功, 游戏即将重启')
                self.click(self.find_boxes(texts, match="确认"), after_sleep=30)
                result = self.start_device()
                self.log_info(f'start_device end {result}')
                self.sleep(30)
                return False
            if start := self.find_boxes(texts, boundary='bottom_right', match=["开始游戏", re.compile("进入游戏")]):
                if not self.find_boxes(texts, boundary='bottom_right', match="登录"):
                    self.click(start)
                    self.log_info(f'点击开始游戏! {start}')
                    return False

    def in_team_and_world(self):
        return self.in_team()[
            0]  # and self.find_one(f'gray_book_button', threshold=0.7, canny_lower=50, canny_higher=150)

    def get_angle_between(self, my_angle, angle):
        if my_angle > angle:
            to_turn = angle - my_angle
        else:
            to_turn = -(my_angle - angle)
        if to_turn > 180:
            to_turn -= 360
        elif to_turn < -180:
            to_turn += 360
        return to_turn

    def get_my_angle(self):
        return self.rotate_arrow_and_find()[0]

    def rotate_arrow_and_find(self):
        arrow_template = self.get_feature_by_name('arrow')
        original_mat = arrow_template.mat
        max_conf = 0
        max_angle = 0
        max_target = None
        max_mat = None
        (h, w) = arrow_template.mat.shape[:2]
        # self.log_debug(f'turn_east h:{h} w:{w}')
        center = (w // 2, h // 2)
        target_box = self.get_box_by_name('arrow')
        # if self.debug:
        #     self.screenshot('arrow_original', original_ mat)
        for angle in range(0, 360):
            # Rotate the template image
            rotation_matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
            template = cv2.warpAffine(original_mat, rotation_matrix, (w, h))
            # mask = np.where(np.all(template == [0, 0, 0], axis=2), 0, 255).astype(np.uint8)

            target = self.find_one(box=target_box,
                                   template=template, threshold=0.01)
            # if self.debug and angle % 90 == 0:
            #     self.screenshot(f'arrow_rotated_{angle}', arrow_template.mat)
            if target and target.confidence > max_conf:
                max_conf = target.confidence
                max_angle = angle
                max_target = target
                # max_mat = template
        # arrow_template.mat = original_mat
        # arrow_template.mask = None
        # if self.debug and max_mat is not None:
        #     self.screenshot('max_mat',frame=max_mat)
        # self.log_debug(f'turn_east max_conf: {max_conf} {max_angle}')
        return max_angle, max_target

    def get_mini_map_turn_angle(self, feature, threshold=0.72, x_offset=0, y_offset=0):
        box = self.get_box_by_name('box_minimap')
        target = self.find_one(feature, box=box, threshold=threshold)
        if not target:
            self.log_info(f'Can not find {feature} on minimap')
            return None
        else:
            self.log_debug(f'found {box} on minimap')
        target.x += target.width * x_offset
        target.y += target.height * y_offset
        direction_angle = calculate_angle_clockwise(box, target)
        my_angle = self.get_my_angle()
        to_turn = self.get_angle_between(my_angle, direction_angle)
        self.log_info(f'angle: {my_angle}, to_turn: {to_turn}')
        return to_turn

    def _stop_movement(self, current_direction):
        """Releases keys and mouse to stop character movement."""
        if current_direction is not None:
            self.mouse_up(key='right')
            self.send_key_up(current_direction)

    def _navigate_based_on_angle(self, angle, current_direction, current_adjust):
        """
        Core navigation logic to adjust movement based on a target angle.
        This contains the shared logic from the original functions.

        Returns a tuple: (new_direction, new_adjust, should_continue)
        - new_direction: The updated movement direction ('w', 'a', 's', 'd').
        - new_adjust: The updated adjustment state.
        - should_continue: A boolean indicating if the calling loop should `continue`.
        """
        # 1. Handle minor adjustments if already moving forward
        if current_direction == 'w':
            if 10 <= angle <= 80:
                minor_adjust = 'd'
            elif -80 <= angle <= -10:
                minor_adjust = 'a'
            else:
                minor_adjust = None

            if minor_adjust:
                self.send_key_down(minor_adjust)
                self.sleep(0.1)
                self.middle_click(down_time=0.1)
                self.send_key_up(minor_adjust)
                self.sleep(0.01)
                # Tell the caller to continue to the next loop iteration
                return current_direction, current_adjust, True

        # 2. Clean up any previous adjustments
        if current_adjust:
            self.send_key_up(current_adjust)
            current_adjust = None

        # 3. Determine the major new direction based on the angle
        if -45 <= angle <= 45:
            new_direction = 'w'
        elif 45 < angle <= 135:
            new_direction = 'd'
        elif -135 < angle <= -45:
            new_direction = 'a'
        else:
            new_direction = 's'

        # 4. Change direction if needed
        if current_direction != new_direction:
            self.log_info(f'changed direction {angle} {current_direction} -> {new_direction}')
            if current_direction:
                self.mouse_up(key='right')
                self.send_key_up(current_direction)
                self.wait_until(self.in_combat, time_out=0.2)
            self.turn_direction(new_direction)
            self.send_key_down('w')
            self.wait_until(self.in_combat, time_out=0.2)
            self.mouse_down(key='right')
            current_direction = 'w'  # After turning, we always move forward
            self.wait_until(self.in_combat, time_out=1)

        return current_direction, current_adjust, False

    def in_team(self):
        c1 = self.find_one('char_1_text',
                           threshold=0.8)
        c2 = self.find_one('char_2_text',
                           threshold=0.8)
        c3 = self.find_one('char_3_text',
                           threshold=0.8)
        arr = [c1, c2, c3]
        # logger.debug(f'in_team check {arr}')
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
        if '鸣潮' in self.hwnd_title or self.is_browser():
            return 'zh_CN'
        elif 'Wuthering' in self.hwnd_title:
            return 'en_US'
        elif '鳴潮' in self.hwnd_title:
            return 'zh_TW'
        return 'unknown_lang'

    def open_esc_menu(self):
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.95, 0.04)
        self.send_key_up('alt')
        self.sleep(0.5)

    def openF2Book(self, feature="gray_book_all_monsters", opened=False):
        if not opened:
            self.log_info('click f2 to open the book')
            self.send_key_down('alt')
            self.sleep(0.05)
            self.click_relative(0.77, 0.05)
            self.sleep(0.02)
            self.send_key_up('alt')
            self.sleep(1)
        if self.in_team_and_world():
            self.send_key('f2', after_sleep=1)
            self.log_info('send f2 key to open the book')
        gray_book_boss = self.wait_book(feature)
        self.sleep(0.8)
        if not gray_book_boss:
            self.log_error("can't find gray_book_boss, make sure f2 is the hotkey for book", notify=True)
            raise Exception("can't find gray_book_boss, make sure f2 is the hotkey for book")
        return gray_book_boss

    def click_traval_button(self):
        for feature_name in ['fast_travel_custom', 'gray_teleport', 'remove_custom']:
            if feature := self.find_one(feature_name, threshold=0.7):
                self.sleep(0.5)
                self.click(feature, after_sleep=1)
                if feature.name == 'fast_travel_custom':
                    if confirm := self.wait_feature(
                            ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                            raise_if_not_found=False,
                            threshold=0.6,
                            time_out=2):
                        self.click(0.49, 0.55, after_sleep=0.5)  # 点击不再提醒
                        self.click(confirm, after_sleep=0.5)
                        self.wait_click_feature(
                            ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                            relative_x=-1, raise_if_not_found=False,
                            threshold=0.6,
                            time_out=1)
                return True

    def wait_click_travel(self):
        self.wait_until(self.click_traval_button, raise_if_not_found=True, time_out=10)

    def wait_book(self, feature="gray_book_all_monsters", time_out=3):
        gray_book_boss = self.wait_until(
            lambda: self.find_one(feature, vertical_variance=0.8, horizontal_variance=0.05,
                                  threshold=0.3),
            time_out=time_out, settle_time=1)
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

    def click_on_book_target(self, serial_number: int, total_number: int):
        double_bar_top = 333 / 1440
        bar_top = 268 / 1440
        bar_bottom = 1259 / 1440
        container_max_rows = 5
        default_container_display = 398 / 992 * 12
        index = serial_number - 1
        if serial_number <= container_max_rows:
            x = 0.88
            y = 0.28
            height = (0.85 - 0.28) / 4
            y += height * index
            self.click_relative(x, y, after_sleep=1)
        else:
            min_width = self.width_of_screen(475 / 2560)
            min_height = self.height_of_screen(40 / 1440)
            double = find_color_rectangles(self.frame, double_drop_color, min_width, min_height,
                                           box=self.box_of_screen(1990 / 2560, 170 / 1440, 2500 / 2560, 245 / 1440))
            if double:
                logger.info(f'double drop!')
                bar_top = double_bar_top
                self.draw_boxes('double_drop', double, color='blue')
            gap_per_index = (bar_bottom - bar_top) / total_number
            y = gap_per_index * (serial_number - container_max_rows + default_container_display) + bar_top
            self.click_relative(0.98, y)
            logger.info(f'scroll to target')
            btns = self.find_feature('boss_proceed', box=self.box_of_screen(0.94, 0.6, 0.97, 0.88), threshold=0.8)
            if btns is None:
                raise Exception("can't find boss_proceed")
            bottom_btn = max(btns, key=lambda box: box.y)
            self.click_box(bottom_btn, after_sleep=1)
        self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom'], time_out=10, settle_time=0.5)

    def change_time_to_night(self):
        logger.info('change time to night')
        self.send_key("esc")
        self.sleep(1)
        self.click_relative(0.71, 0.96)
        self.sleep(2)
        self.click_relative(0.19, 0.14)
        self.sleep(1)

        # 调整时间到晚上
        for _ in range(3):
            self.click_relative(0.82, 0.53)
            self.sleep(1)

        self.click_relative(0.52, 0.90)
        self.sleep(6)
        self.send_key("esc")
        self.sleep(1)
        self.send_key("esc")
        self.sleep(1)

    def jump(self, after_sleep=0.01):
        self.send_key(self.key_config.get('Jump Key'), after_sleep=after_sleep)


double_drop_color = {
    'r': (140, 180),  # Red range
    'g': (120, 160),  # Green range
    'b': (70, 110)  # Blue range
}

echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}


def calculate_angle_clockwise(box1, box2):
    """
    Calculates angle (radians) from horizontal right to line (x1,y1)->(x2,y2).
    Positive clockwise, negative counter-clockwise.
    """
    x1, y1 = box1.center()
    x2, y2 = box2.center()
    dx = x2 - x1
    dy = y2 - y1
    # math.atan2(dy, dx) gives angle from positive x-axis, positive CCW.
    # Negate for positive CW convention.

    degree = math.degrees(math.atan2(dy, dx))
    if degree < 0:
        degree += 360
    return degree


lower_white = np.array([244, 244, 244], dtype=np.uint8)
lower_white_none_inclusive = np.array([243, 243, 243], dtype=np.uint8)
upper_white = np.array([255, 255, 255], dtype=np.uint8)
black = np.array([0, 0, 0], dtype=np.uint8)


def isolate_white_text_to_black(cv_image):
    """
    Converts pixels in the near-white range (244-255) to black,
    and all others to white.
    Args:
        cv_image: Input image (NumPy array, BGR).
    Returns:
        Black and white image (NumPy array), where matches are black.
    """
    match_mask = cv2.inRange(cv_image, black, lower_white_none_inclusive)
    output_image = cv2.cvtColor(match_mask, cv2.COLOR_GRAY2BGR)

    return output_image


def convert_bw(cv_image):
    match_mask = cv2.inRange(cv_image, lower_white, upper_white)
    output_image = cv2.cvtColor(match_mask, cv2.COLOR_GRAY2BGR)
    return output_image


lower_icon_white = np.array([210, 210, 210], dtype=np.uint8)
upper_icon_white = np.array([244, 244, 244], dtype=np.uint8)


def convert_dialog_icon(cv_image):
    match_mask = cv2.inRange(cv_image, lower_icon_white, upper_icon_white)
    output_image = cv2.cvtColor(match_mask, cv2.COLOR_GRAY2BGR)
    return output_image


def binarize_for_matching(image):
    """
    Converts a colored image to a binary image based on a brightness threshold.

    The rule is: pixels with a value of 240-255 become pure white (255),
    and all other pixels become pure black (0).

    Args:
        image (np.array): The input BGR image from OpenCV.

    Returns:
        np.array: The resulting binary image (single channel, 8-bit).
    """
    # Convert the image to grayscale for a single brightness value per pixel.
    # This is more robust than checking individual R, G, B channels.

    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply the binary threshold.
    # Pixels > 239 will be set to 255 (white).
    # Pixels <= 239 will be set to 0 (black).
    # cv2.THRESH_BINARY is the type of thresholding we want.
    _, binary_image = cv2.threshold(gray_image, 244, 255, cv2.THRESH_BINARY)
    return binary_image
