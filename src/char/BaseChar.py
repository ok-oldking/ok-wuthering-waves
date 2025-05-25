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
        self.freeze_durations = []
        self.last_perform = 0
        self.current_con = 0
        self.has_tool_box = False

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
        if duration < 0:
            duration = time.time() - start
        if start > 0 and duration > freeze_time:
            current_time = time.time()
            self.freeze_durations = [item for item in self.freeze_durations if item[0] <= current_time - 15]
            self.freeze_durations.append((start, duration, freeze_time))

    def time_elapsed_accounting_for_freeze(self, start):
        to_minus = 0
        for freeze_start, duration, freeze_time in self.freeze_durations:
            if start < freeze_start:
                to_minus += duration - freeze_time
        if to_minus != 0:
            self.logger.debug(f'time_elapsed_accounting_for_freeze to_minus {to_minus}')
        return time.time() - start - to_minus

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

    def count_gray_forte(self, left=0.42, right=0.57):
        image = self.task.box_of_screen(left, 0.92, right, 0.94).crop_frame(self.task.frame)
        # if self.task.debug:
        #     self.task.screenshot("forte", image) # Original commented-out screenshot

        # debug_image = image.copy()
        debug_image = None

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        lower_gray = np.array([0, 10, 140])
        upper_gray = np.array([360, 95, 255])

        mask = cv2.inRange(hsv, lower_gray, upper_gray)

        if debug_image is not None:
            self.task.screenshot("forte_mask", mask)

        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        mask_opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open, iterations=1)

        if debug_image is not None:
            self.task.screenshot("forte_mask2", mask_opened)

        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        mask_processed = cv2.dilate(mask_opened, kernel_dilate, iterations=1)

        if debug_image is not None:
            self.task.screenshot("forte_mask3", mask_processed)

        contours, _ = cv2.findContours(mask_processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        potential_rects = []

        # debug_image = None
        min_area = 0.000001
        max_area = 0.00002
        min_aspect_ratio_wh = 0.2
        max_aspect_ratio_wh = 1.5

        for cnt in contours:
            area_raw = cv2.contourArea(cnt)
            normalized_area = area_raw / self.task.screen_width / self.task.screen_height

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio_wh = float(w) / h if h != 0 else float(
                'inf') if w != 0 else 0  # Avoid division by zero if h is 0
            self.task.log_debug(
                f'Contour: x={x},y={y},w={w},h={h}, Area (norm): {normalized_area:.10f}, AR: {aspect_ratio_wh:.2f}')

            if min_area < normalized_area < max_area:
                if h == 0:  # Original code had this check, if h=0, aspect ratio calculation modified above
                    if debug_image is not None:
                        cv2.rectangle(debug_image, (x, y), (x + w, y + h), (255, 0, 255), 1)
                    continue

                if min_aspect_ratio_wh < aspect_ratio_wh < max_aspect_ratio_wh:
                    potential_rects.append((x, y, w, h))
                    if debug_image is not None:
                        cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 255), 1)
                elif debug_image is not None:
                    cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 0, 255), 1)
            elif debug_image is not None:
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), (255, 0, 0), 1)

        if not potential_rects:
            if debug_image is not None:
                self.task.screenshot("debug_image", debug_image)
            return 0

        sorted_rects = sorted(potential_rects, key=lambda r: r[0], reverse=True)

        final_count = 0
        final_counted_rects_list = []
        last_counted_rect_params = None

        image_width = image.shape[1]  # Width of the cropped image

        for i in range(len(sorted_rects)):
            current_rect_params = sorted_rects[i]
            x_curr, y_curr, w_curr, h_curr = current_rect_params

            if w_curr == 0 and min_aspect_ratio_wh > 0:
                # self.task.log_debug(
                #     f"Warning: Encountered rectangle with zero width at x={x_curr} after initial filters.")
                continue

            if last_counted_rect_params is None:
                if x_curr > 0.9 * image_width:
                    last_counted_rect_params = current_rect_params
                    final_count = 1
                    final_counted_rects_list.append(current_rect_params)
                    # self.task.log_debug(
                    #     f"Starting continuous sequence with rect at x={x_curr}, w={w_curr}. "
                    #     f"(Passed >0.9 width check: x_curr={x_curr} > threshold={0.9 * image_width:.2f} for image_width={image_width}).")
                else:
                    # self.task.log_debug(
                    #     f"Rightmost rectangle at x={x_curr} (w={w_curr}) does not meet start condition: "
                    #     f"x_curr={x_curr} is not > threshold={0.9 * image_width:.2f} (image_width={image_width}). Sequence cannot start."
                    # )
                    if debug_image is not None:
                        cv2.rectangle(debug_image, (x_curr, y_curr), (x_curr + w_curr, y_curr + h_curr), (128, 0, 128),
                                      1)
                    break
            else:
                x_last, y_last, w_last, h_last = last_counted_rect_params

                gap = x_last - (x_curr + w_curr)
                distance_threshold = 4 * w_curr
                x_gap_condition_met = (0 <= gap <= distance_threshold)

                y_center_last = y_last + h_last / 2.0
                y_center_curr = y_curr + h_curr / 2.0
                y_center_distance = abs(y_center_curr - y_center_last)

                y_alignment_condition_met = y_center_distance < w_curr

                # self.task.log_debug(
                #    f"Rect[{i}] (x={x_curr},y={y_curr},w={w_curr},h={h_curr}) vs Last (x={x_last},y={y_last},w={w_last},h={h_last}). "
                #    f"X_Gap: {gap:.1f} (Thres:{distance_threshold:.1f}) Met:{x_gap_condition_met}. "
                #    f"Y_Dist: {y_center_distance:.1f} (Thres(w_curr):{w_curr:.1f}) Met:{y_alignment_condition_met}."
                # )

                if x_gap_condition_met and y_alignment_condition_met:
                    last_counted_rect_params = current_rect_params
                    final_count += 1
                    final_counted_rects_list.append(current_rect_params)
                    # self.task.log_debug(
                    #     f"Added rect at x={x_curr} to sequence. Current count: {final_count}.")
                else:
                    # log_message_parts = [f"Sequence broken. Candidate rect at x={x_curr}, w={w_curr}."]
                    # if not x_gap_condition_met:
                    #     log_message_parts.append(f"X Gap condition failed: gap {gap:.2f} not in [0, {distance_threshold:.2f}].")
                    # if not y_alignment_condition_met:
                    #     log_message_parts.append(f"Y Alignment condition failed: y_center_distance {y_center_distance:.2f} not < w_curr {w_curr:.2f} (actual w_curr).")
                    # self.task.log_debug(" ".join(log_message_parts))
                    break

        if debug_image is not None:
            for rect_params in final_counted_rects_list:
                x, y, w, h = rect_params
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            self.task.screenshot("debug_image", debug_image)

        return final_count

    def count_all_forte(self):
        """
        Counts all pill-shaped segments in a progress bar image based on geometry,
        regardless of their color.
        """
        # Assuming self.task and its methods are defined and initialized.
        image = self.task.box_of_screen(0.41, 0.90, 0.57, 0.94).crop_frame(self.task.frame)

        h_img, w_img = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur - (3,3) kernel is chosen to reduce noise
        # while trying to preserve details of small oval shapes.
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Edge Detection using Canny
        # Thresholds (50, 150) are common starting points.
        edges = cv2.Canny(blurred, 50, 150)

        # Find Contours
        # cv2.RETR_EXTERNAL retrieves only the extreme outer contours.
        # cv2.CHAIN_APPROX_SIMPLE compresses contour segments.
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        progress_ovals_count = 0
        badge_icons_count = 0

        for cnt in contours:
            area = cv2.contourArea(cnt)

            # Filter out very small contours early to reduce processing
            if area < 20:  # Adjusted minimum area threshold
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            if w == 0 or h == 0:
                continue

            aspect_ratio_bbox = float(w) / h
            perimeter = cv2.arcLength(cnt, True)

            if perimeter == 0:  # Avoid division by zero for degenerate contours
                continue

            # Approximate contour to a polygon
            # Epsilon factor (0.03) determines the precision of approximation.
            approx = cv2.approxPolyDP(cnt, 0.03 * perimeter, True)
            num_vertices = len(approx)

            centroid_y = y + h / 2.0  # Use float division for centroid

            # Criteria for Badge Icons ("gray rectangle shapes")
            # These are typically larger, at the top, and have 5-8 vertices.
            is_badge_icon = False
            if (centroid_y < h_img * 0.45) and \
                    (1500 < area < 4500) and \
                    (0.6 < aspect_ratio_bbox < 1.4) and \
                    (5 <= num_vertices <= 8):  # Pentagonal to octagonal shapes
                badge_icons_count += 1
                is_badge_icon = True

            # Criteria for Progress Ovals ("purple rectangle shapes")
            # These are smaller, in the middle/lower part, more circular/oval.
            # Check only if not already classified as a badge.
            if not is_badge_icon:
                if (h_img * 0.55 < centroid_y < h_img * 0.70) and \
                        (40 < area < 200) and \
                        (0.5 < aspect_ratio_bbox < 2.0) and \
                        (num_vertices >= 6):  # Ovals/circles tend to have more vertices after approximation

                    # Solidity check helps confirm "roundness" or "fullness" of the shape.
                    # Ovals should be highly convex.
                    hull = cv2.convexHull(cnt)
                    if cv2.contourArea(hull) > 0:  # Avoid division by zero
                        solidity = area / cv2.contourArea(hull)
                        if solidity > 0.85:
                            progress_ovals_count += 1

        return progress_ovals_count, badge_icons_count


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
