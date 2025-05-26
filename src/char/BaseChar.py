import time
from enum import IntEnum, StrEnum
from typing import Any

import cv2
import numpy as np

from ok import Config, Logger
from src import text_white_color


class Priority(IntEnum):
    MIN = -999999999
    SWITCH_CD = -1000
    CURRENT_CHAR = -100
    CURRENT_CHAR_PLUS = CURRENT_CHAR + 1
    SKILL_AVAILABLE = 100
    ALL_IN_CD = 0
    NORMAL = 10
    MAX = 9999999999


class Role(StrEnum):
    DEFAULT = 'Default'
    SUB_DPS = 'Sub DPS'
    MAIN_DPS = 'Main DPS'
    HEALER = 'Healer'


role_values = [role for role in Role]

char_lib_check_marks = ['char_1_lib_check_mark', 'char_2_lib_check_mark', 'char_3_lib_check_mark']


class BaseChar:

    def __init__(self, task, index, res_cd=20, echo_cd=20, liberation_cd=25, char_name=None):
        self.white_off_threshold = 0.01
        self.echo_cd = echo_cd
        self.task = task
        self.liberation_cd = liberation_cd
        self.sleep_adjust = 0
        self.char_name = char_name
        self.index = index
        self.ring_index = -1  # for con check
        self.last_switch_time = -1
        self.last_res = -1
        self.last_echo = -1
        self.last_liberation = -1
        self.has_intro = False
        self.res_cd = res_cd
        self.is_current_char = False
        self._liberation_available = False
        self._resonance_available = False
        self._echo_available = False
        self.logger = Logger.get_logger(self.name)
        self.full_ring_area = 0
        self.last_perform = 0
        self.current_con = 0
        self.has_tool_box = False
        self.intro_motion_freeze_duration = 0.9
        self.last_outro_time = -1

    def skip_combat_check(self):
        return False

    def use_tool_box(self):
        if self.has_tool_box:
            self.task.send_key('t')
            self.has_tool_box = False

    @property
    def name(self):
        return self.__class__.__name__

    def __eq__(self, other):
        if isinstance(other, BaseChar):
            return self.name == other.name and self.index == other.index
        return False

    def perform(self):
        # self.wait_down()
        self.last_perform = time.time()
        self.do_perform()
        self.logger.debug(f'set current char false {self.index}')

    def wait_down(self):
        while self.flying():
            self.task.click()
            self.sleep(0.2)

    def wait_intro(self, time_out=1.2, click=True):
        if self.has_intro:
            self.task.wait_until(self.down, post_action=self.click_with_interval if click else None, time_out=time_out)

    def down(self):
        return (self.current_resonance() > 0 and not self.has_cd('resonance')) or (
                self.current_liberation() > 0 and not self.has_cd('liberation'))

    def click_with_interval(self, interval=0.1):
        self.click(interval=interval)

    def click(self, *args: Any, **kwargs: Any):
        self.task.click(*args, **kwargs)

    def do_perform(self):
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.continues_normal_attack(1.2, click_resonance_if_ready_and_return=True)
        self.click_liberation(con_less_than=1)
        if self.click_resonance()[0]:
            return self.switch_next_char()
        if self.click_echo():
            return self.switch_next_char()
        self.continues_normal_attack(0.31)
        self.switch_next_char()

    def has_cd(self, box_name):
        return self.task.has_cd(box_name)

    def is_available(self, percent, box_name):
        return percent == 0 or not self.has_cd(box_name)

    def switch_out(self):
        self.last_switch_time = time.time()
        self.is_current_char = False
        self.has_intro = False
        if self.current_con == 1:
            self.logger.info(f'switch_out at full con set current_con to 0')
            self.current_con = 0

    def __repr__(self):
        return self.__class__.__name__

    def switch_next_char(self, post_action=None, free_intro=False, target_low_con=False):
        self.is_forte_full()
        self.has_intro = False
        self._liberation_available = self.liberation_available()
        self.use_tool_box()
        self.task.switch_next_char(self, post_action=post_action, free_intro=free_intro,
                                   target_low_con=target_low_con)

    def sleep(self, sec, check_combat=True):
        if sec > 0:
            self.task.sleep_check_combat(sec + self.sleep_adjust, check_combat=check_combat)

    def click_resonance(self, post_sleep=0, has_animation=False, send_click=True, animation_min_duration=0,
                        check_cd=False):
        clicked = False
        self.logger.debug(f'click_resonance start')
        last_click = 0
        last_op = 'click'
        resonance_click_time = 0
        animated = False
        start = time.time()
        while True:
            if resonance_click_time != 0 and time.time() - resonance_click_time > 8:
                self.task.in_liberation = False
                self.logger.error(f'click_resonance too long, breaking {time.time() - resonance_click_time}')
                self.task.screenshot('click_resonance too long, breaking')
                break
            if has_animation:
                if not self.task.in_team()[0]:
                    self.task.in_liberation = True
                    animated = True
                    if time.time() - resonance_click_time > 6:
                        self.task.in_liberation = False
                        self.logger.error(f'resonance animation too long, breaking')
                    self.task.next_frame()
                    self.check_combat()
                    continue
                else:
                    self.task.in_liberation = False
            self.check_combat()
            now = time.time()
            current_resonance = self.current_resonance()
            if not self.resonance_available(current_resonance, check_cd=check_cd) and (
                    not has_animation or now - start > animation_min_duration):
                self.logger.debug(f'click_resonance not available break')
                break
            self.logger.debug(f'click_resonance resonance_available click {current_resonance}')

            if now - last_click > 0.1:
                if send_click and (current_resonance == 0 or last_op == 'resonance'):
                    self.task.click()
                    last_op = 'click'
                    continue
                if current_resonance > 0 and self.resonance_available(current_resonance):
                    if resonance_click_time == 0:
                        clicked = True
                        resonance_click_time = now
                        self.update_res_cd()
                    last_op = 'resonance'
                    self.send_resonance_key()
                    if has_animation:  # sleep if there will be an animation like Jinhsi
                        self.sleep(0.2, check_combat=False)
                last_click = now
            self.task.next_frame()
        self.task.in_liberation = False
        if clicked:
            self.sleep(post_sleep)
        duration = time.time() - resonance_click_time if resonance_click_time != 0 else 0
        if animated:
            self.add_freeze_duration(resonance_click_time, duration)
        self.logger.debug(f'click_resonance end clicked {clicked} duration {duration} animated {animated}')
        return clicked, duration, animated

    def send_resonance_key(self, post_sleep=0, interval=-1, down_time=0.01):
        self._resonance_available = False
        self.task.send_key(self.get_resonance_key(), interval=interval, down_time=down_time, after_sleep=post_sleep)

    def send_echo_key(self, after_sleep=0, interval=-1, down_time=0.01):
        self._echo_available = False
        self.task.send_key(self.get_echo_key(), interval=interval, down_time=down_time, after_sleep=after_sleep)

    def send_liberation_key(self, after_sleep=0, interval=-1, down_time=0.01):
        self._liberation_available = False
        self.task.send_key(self.get_liberation_key(), interval=interval, down_time=down_time, after_sleep=after_sleep)

    def update_res_cd(self):
        current = time.time()
        if current - self.last_res > self.res_cd:  # count the first click only
            self.last_res = time.time()

    def update_liberation_cd(self):
        current = time.time()
        if current - self.last_liberation > (self.liberation_cd - 2):  # count the first click only
            self.last_liberation = time.time()

    def update_echo_cd(self):
        current = time.time()
        if current - self.last_echo > self.echo_cd:  # count the first click only
            self.last_echo = time.time()

    def click_echo(self, duration=0, sleep_time=0, time_out=1):
        self.logger.debug(f'click_echo start duration: {duration}')
        if self.has_cd('echo'):
            self.logger.debug('click_echo has cd return ')
            return False
        clicked = False
        start = time.time()
        last_click = 0
        time_out += duration
        while True:
            if time.time() - start > time_out:
                self.logger.info('click_echo time out')
                return False
            self.check_combat()
            current = self.current_echo()
            if not self.echo_available(current) and (duration == 0 or not clicked):
                break
            now = time.time()
            if duration > 0 and start != 0:
                if now - start > duration:
                    break
            if now - last_click > 0.1:
                if not clicked:
                    self.update_echo_cd()
                    clicked = True
                self.send_echo_key()
                last_click = now
            if now - start > 5:
                self.logger.error(f'click_echo too long {clicked}')
                break
            self.task.next_frame()
        self.logger.debug(f'click_echo end {clicked}')
        return clicked

    def check_combat(self):
        self.task.check_combat()

    def reset_state(self):
        self.has_intro = False
        self.has_tool_box = False
        self._liberation_available = False
        self._echo_available = False
        self._resonance_available = False

    def click_liberation(self, con_less_than=-1, send_click=False, wait_if_cd_ready=0, timeout=5):
        if con_less_than > 0:
            if self.get_current_con() > con_less_than:
                return False
        self.logger.debug(f'click_liberation start')
        start = time.time()
        last_click = 0
        clicked = False
        while time.time() - start < wait_if_cd_ready and not self.liberation_available() and not self.has_cd(
                'liberation'):
            self.logger.debug(f'click_liberation wait ready {wait_if_cd_ready}')
            if send_click:
                self.click(interval=0.1)
            self.task.next_frame()
        while self.liberation_available():  # clicked and still in team wait for animation
            self.logger.debug(f'click_liberation liberation_available click')
            now = time.time()
            if now - last_click > 0.1:
                self.send_liberation_key()
                if not clicked:
                    clicked = True
                    self.update_liberation_cd()
                last_click = now
            if time.time() - start > timeout:
                self.task.raise_not_in_combat('too long clicking a liberation')
            self.task.next_frame()
        if clicked:
            if self.task.wait_until(lambda: not self.task.in_team()[0], time_out=0.4):
                self.task.in_liberation = True
                self.logger.debug(f'not in_team successfully casted liberation')
            else:
                self.task.in_liberation = False
                self.logger.error(f'clicked liberation but no effect')
                return False
        start = time.time()
        while not self.task.in_team()[0]:
            self.task.in_liberation = True
            if not clicked:
                clicked = True
                self.update_liberation_cd()
            if send_click:
                self.click(interval=0.1)
            if time.time() - start > 7:
                self.task.in_liberation = False
                self.task.raise_not_in_combat('too long a liberation, the boss was killed by the liberation')
            self.task.next_frame()
        duration = time.time() - start
        self.add_freeze_duration(start, duration)
        self.task.in_liberation = False
        if clicked:
            self.logger.info(f'click_liberation end {duration}')
        return clicked

    def on_combat_end(self, chars):
        pass

    def add_freeze_duration(self, start, duration=-1.0, freeze_time=0.1):
        self.task.add_freeze_duration(start, duration, freeze_time)

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return self.task.time_elapsed_accounting_for_freeze(start, intro_motion_freeze)

    def get_liberation_key(self):
        return self.task.get_liberation_key()

    def has_long_actionbar(self):
        return False

    def get_echo_key(self):
        return self.task.get_echo_key()

    def get_resonance_key(self):
        return self.task.get_resonance_key()

    def get_switch_priority(self, current_char, has_intro, target_low_con):
        priority = self.do_get_switch_priority(current_char, has_intro, target_low_con)
        if priority < Priority.MAX and time.time() - self.last_switch_time < 0.9 and not has_intro:
            return Priority.SWITCH_CD  # switch cd
        else:
            return priority

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        priority = 0
        if self.count_liberation_priority() and self.liberation_available():
            priority += self.count_liberation_priority()
        if self.count_resonance_priority() and self.resonance_available():
            priority += self.count_resonance_priority()
        if self.count_forte_priority():
            priority += self.count_forte_priority()
        if self.echo_available():
            priority += self.count_echo_priority()
        if priority > 0:
            priority += Priority.SKILL_AVAILABLE
        priority += self.count_liberation_priority()
        return priority

    def count_base_priority(self):
        return 0

    def count_liberation_priority(self):
        return 1

    def count_resonance_priority(self):
        return 10

    def count_echo_priority(self):
        return 1

    def count_forte_priority(self):
        return 0

    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        if check_cd and time.time() - self.last_res > self.res_cd:
            return True
        if self._resonance_available:
            return True
        if self.is_current_char:
            snap = self.current_resonance() if current is None else current
            if check_ready and snap == 0:
                return False
            self._resonance_available = self.is_available(snap, 'resonance')
        elif self.res_cd > 0:
            return time.time() - self.last_res > self.res_cd
        return self._resonance_available

    def liberation_cd_ready(self, offset=1):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation + 1) >= self.liberation_cd

    def echo_available(self, current=None):
        if self.is_current_char:
            if self._echo_available:
                return True
            snap = self.current_echo() if current is None else current
            self._echo_available = self.is_available(snap, 'echo')
            return self._echo_available
        elif self.echo_cd > 0:
            return time.time() - self.last_echo > self.echo_cd

    def is_con_full(self):
        return self.task.is_con_full()

    def get_current_con(self):
        self.current_con = self.task.get_current_con()
        return self.current_con

    def is_forte_full(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 2251, 1993, 2311, 2016, name='forte_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        # num_labels, stats = get_connected_area_by_color(box.crop_frame(self.task.frame), forte_white_color,
        #                                                 connectivity=8)
        # total_area = 0
        # for i in range(1, num_labels):
        #     # Check if the connected co  mponent touches the border
        #     left, top, width, height, area = stats[i]
        #     total_area += area
        # white_percent = total_area / box.width / box.height
        # if self.task.debug:
        #     self.task.screenshot(f'{self}_forte_{white_percent}')
        # self.logger.debug(f'is_forte_full {white_percent}')
        box.confidence = white_percent
        self.task.draw_boxes('forte_full', box)
        return white_percent > 0.08

    def liberation_available(self):
        if self._liberation_available:
            return True
        if self.is_current_char:
            snap = self.current_liberation()
            if snap == 0:
                return False
            else:
                self._liberation_available = self.is_available(snap, 'liberation')
        return self._liberation_available

    def __str__(self):
        return self.__repr__()

    def continues_normal_attack(self, duration, interval=0.1, click_resonance_if_ready_and_return=False,
                                until_con_full=False):
        start = time.time()
        while time.time() - start < duration:
            if click_resonance_if_ready_and_return and self.resonance_available():
                return self.click_resonance()
            if until_con_full and self.is_con_full():
                return
            self.task.click(interval=interval)

    def continues_click(self, key, duration, interval=0.1):
        start = time.time()
        while time.time() - start < duration:
            self.task.send_key(key, interval=interval)

    def normal_attack(self):
        self.logger.debug('normal attack')
        self.check_combat()
        self.task.click()

    def heavy_attack(self, duration=0.6):
        self.check_combat()
        self.logger.debug('heavy attack start')
        self.task.mouse_down()
        self.sleep(duration)
        self.task.mouse_up()
        self.logger.debug('heavy attack end')

    def current_resonance(self):
        return self.task.calculate_color_percentage(text_white_color,
                                                    self.task.get_box_by_name('box_resonance'))

    def current_echo(self):
        return self.task.calculate_color_percentage(text_white_color,
                                                    self.task.get_box_by_name('box_echo'))

    def current_liberation(self):
        return self.task.calculate_color_percentage(text_white_color, self.task.get_box_by_name('box_liberation'))

    def flying(self):
        return self.current_resonance() == 0

    # def count_rectangle_forte(self, left=0.42, right=0.57):
    #     # Perform image cropping once, as it's independent of saturation ranges
    #     cropped_image_base = self.task.box_of_screen(left, 0.927, right, 0.931).crop_frame(self.task.frame)
    #
    #     if cropped_image_base is None or cropped_image_base.size == 0 or \
    #             cropped_image_base.shape[0] == 0 or cropped_image_base.shape[1] == 0:
    #         self.task.log_debug("Initial cropped image is empty or invalid.")
    #         return (None, None), 0
    #
    #     max_items_found = -1  # Initialize to -1 to distinguish from finding 0 items
    #
    #     current_s_lower = 0
    #     current_s_upper = 40
    #     increment_step = 10
    #
    #     while current_s_upper <= 255:
    #         # Ensure lower saturation is less than upper saturation (should be true with current logic)
    #         if current_s_lower >= current_s_upper:
    #             # self.task.log_debug(
    #             #     f"Skipping invalid saturation range: lower_S={current_s_lower}, upper_S={current_s_upper}")
    #             current_s_lower += increment_step
    #             current_s_upper += increment_step
    #             continue
    #
    #         image = cropped_image_base.copy()  # Use a fresh copy of the cropped image for each iteration
    #
    #         # debug_image = image.copy()
    #         debug_image = None
    #
    #         hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    #
    #         # Define gray range with current saturation values
    #         # Hue range is 0-179 for OpenCV. Value range fixed as per original.
    #         lower_gray = np.array([0, current_s_lower, 140])
    #         upper_gray = np.array([179, current_s_upper, 255])
    #
    #         mask = cv2.inRange(hsv, lower_gray, upper_gray)
    #
    #         if debug_image is not None:
    #             self.task.screenshot(f"forte_mask_S{current_s_lower}_{current_s_upper}", mask)
    #
    #         kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    #         mask_opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
    #
    #         # if debug_image is not None:
    #         #     self.task.screenshot(f"forte_mask2_S{current_s_lower}_{current_s_upper}", mask_opened)
    #
    #         kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    #         mask_processed = cv2.dilate(mask_opened, kernel_dilate, iterations=1)
    #
    #         # if debug_image is not None:
    #         #     self.task.screenshot(f"forte_mask3_S{current_s_lower}_{current_s_upper}", mask_processed)
    #
    #         contours, _ = cv2.findContours(mask_processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    #
    #         potential_rects = []
    #         min_area = 0.000001
    #         max_area = 0.00002
    #         min_aspect_ratio_wh = 0.2
    #         max_aspect_ratio_wh = 1.5
    #
    #         for cnt in contours:
    #             area_raw = cv2.contourArea(cnt)
    #             normalized_area = 0
    #             if self.task.screen_width > 0 and self.task.screen_height > 0:
    #                 normalized_area = area_raw / (self.task.screen_width * self.task.screen_height)
    #             else:
    #                 self.task.log_debug("Screen width or height is zero, cannot normalize area.")
    #                 # normalized_area remains 0, likely filtering out the contour
    #
    #             x, y, w, h = cv2.boundingRect(cnt)
    #             aspect_ratio_wh = float(w) / h if h != 0 else float('inf') if w != 0 else 0
    #
    #             # Verbose logging for each contour can be enabled if needed
    #             # self.task.log_debug(
    #             #     f'S_range:[{current_s_lower},{current_s_upper}] Cnt: x={x},y={y},w={w},h={h},image.shape[1]:{image.shape[0]} Area(N): {normalized_area:.7f}, AR: {aspect_ratio_wh:.2f}')
    #
    #             if min_area < normalized_area < max_area and h > image.shape[0] * 0.8:
    #                 if min_aspect_ratio_wh < aspect_ratio_wh < max_aspect_ratio_wh:
    #                     potential_rects.append((x, y, w, h))
    #                     if debug_image is not None:
    #                         cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 255), 1)  # Cyan for potential
    #                 elif debug_image is not None:
    #                     cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 0, 255), 1)  # Red for failed AR
    #             elif debug_image is not None:
    #                 cv2.rectangle(debug_image, (x, y), (x + w, y + h), (255, 0, 0), 1)  # Blue for failed area
    #
    #         current_iteration_final_count = 0
    #         if not potential_rects:
    #             if debug_image is not None:
    #                 self.task.screenshot(f"debug_image_S{current_s_lower}_{current_s_upper}_no_potential", debug_image)
    #             # current_iteration_final_count remains 0
    #         else:
    #             sorted_rects = sorted(potential_rects, key=lambda r: r[0], reverse=True)
    #             final_counted_rects_list = []
    #             last_counted_rect_params = None
    #
    #             cropped_image_width = image.shape[1]
    #             if cropped_image_width == 0:  # Should have been caught by the initial cropped_image_base check
    #                 current_s_lower += increment_step
    #                 current_s_upper += increment_step
    #                 continue  # Proceed to next saturation range
    #
    #             for i in range(len(sorted_rects)):
    #                 current_rect_params = sorted_rects[i]
    #                 x_curr, y_curr, w_curr, h_curr = current_rect_params
    #
    #                 if w_curr == 0 and min_aspect_ratio_wh > 0:
    #                     continue
    #
    #                 if last_counted_rect_params is None:
    #                     if x_curr > 0.9 * cropped_image_width:
    #                         last_counted_rect_params = current_rect_params
    #                         current_iteration_final_count = 1
    #                         final_counted_rects_list.append(current_rect_params)
    #                     else:
    #                         if debug_image is not None:
    #                             cv2.rectangle(debug_image, (x_curr, y_curr), (x_curr + w_curr, y_curr + h_curr),
    #                                           (128, 0, 128), 1)  # Purple for first rejected
    #                         break
    #                 else:
    #                     x_last, y_last, w_last, h_last = last_counted_rect_params
    #                     gap = x_last - (x_curr + w_curr)
    #                     distance_threshold = 4 * w_curr
    #                     x_gap_condition_met = (0 <= gap <= distance_threshold)
    #
    #                     y_center_last = y_last + h_last / 2.0
    #                     y_center_curr = y_curr + h_curr / 2.0
    #                     y_center_distance = abs(y_center_curr - y_center_last)
    #
    #                     y_alignment_condition_met = (y_center_distance < w_curr) if w_curr > 0 else (
    #                             y_center_distance == 0)
    #
    #                     if x_gap_condition_met and y_alignment_condition_met:
    #                         last_counted_rect_params = current_rect_params
    #                         current_iteration_final_count += 1
    #                         final_counted_rects_list.append(current_rect_params)
    #                     else:
    #                         break
    #
    #             if debug_image is not None:
    #                 for rect_params in final_counted_rects_list:
    #                     x_f, y_f, w_f, h_f = rect_params
    #                     cv2.rectangle(debug_image, (x_f, y_f), (x_f + w_f, y_f + h_f), (0, 255, 0),
    #                                   2)  # Green for final counted
    #                 self.task.screenshot(f"debug_image_S{current_s_lower}_{current_s_upper}_final", debug_image)
    #
    #         # Update best result if current iteration is better
    #         if current_iteration_final_count > max_items_found:
    #             max_items_found = current_iteration_final_count
    #             best_s_lower_final = current_s_lower
    #             best_s_upper_final = current_s_upper
    #             self.task.log_debug(
    #                 f"New best S-range: [{best_s_lower_final}, {best_s_upper_final}], Count: {max_items_found}")
    #
    #         # Move to the next saturation range
    #         current_s_lower += increment_step
    #         current_s_upper += increment_step
    #
    #     if max_items_found == -1:  # No items (count > 0) were found in any iteration
    #         # self.task.log_debug("No forte items found across all tested saturation ranges.")
    #         return 0
    #     else:
    #         # self.task.log_debug(
    #         #     f"Optimal S-range: [{best_s_lower_final}, {best_s_upper_final}] with Count: {max_items_found}")
    #         return max_items_found


forte_white_color = {
    'r': (244, 255),  # Red range
    'g': (246, 255),  # Green range
    'b': (250, 255)  # Blue range
}

dot_color = {
    'r': (195, 255),  # Red range
    'g': (195, 255),  # Green range
    'b': (195, 255)  # Blue range
}
