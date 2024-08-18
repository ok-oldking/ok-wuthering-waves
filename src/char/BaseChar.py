import time
from enum import IntEnum, StrEnum
from typing import Any

import cv2
import numpy as np

from ok.color.Color import color_range_to_bound
from ok.config.Config import Config
from ok.logging.Logger import get_logger
from src import text_white_color


class Priority(IntEnum):
    MIN = -999999999
    SWITCH_CD = -1000
    CURRENT_CHAR = -100
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

    def __init__(self, task, index, res_cd=20, echo_cd=20):
        self.white_off_threshold = 0.01
        self.echo_cd = echo_cd
        self.task = task
        self.sleep_adjust = 0
        self.index = index
        self.last_switch_time = -1
        self.last_res = -1
        self.last_echo = -1
        self.has_intro = False
        self.res_cd = res_cd
        self.is_current_char = False
        self.liberation_available_mark = False
        self.logger = get_logger(self.name)
        self.full_ring_area = 0
        self.freeze_durations = []
        self.last_perform = 0
        self._is_forte_full = False
        self.config = {"_full_ring_area": 0, "_ring_color_index": -1}
        if type(self) is not BaseChar:
            self.config = Config(self.name, self.config)
        self.current_con = 0

    def char_config(self):
        return {}

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
        self.liberation_available_mark = self.liberation_available()
        self.task.switch_next_char(self, post_action=post_action, free_intro=free_intro,
                                   target_low_con=target_low_con)

    def sleep(self, sec, check_combat=True):
        if sec > 0:
            self.task.sleep_check_combat(sec + self.sleep_adjust, check_combat=check_combat)

    def click_resonance(self, post_sleep=0, has_animation=False, send_click=True, animation_min_duration=0):
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
            if not self.resonance_available(current_resonance) and (
                    not has_animation or now - start > animation_min_duration):
                self.logger.debug(f'click_resonance not available break')
                break
            self.logger.debug(f'click_resonance resonance_available click {current_resonance}')

            if now - last_click > 0.1:
                if ((current_resonance == 0) and send_click) or last_op == 'resonance':
                    self.task.click()
                    last_op = 'click'
                    continue
                if current_resonance > 0:
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
        self.logger.info(f'click_resonance end clicked {clicked} duration {duration} animated {animated}')
        return clicked, duration, animated

    def send_resonance_key(self, post_sleep=0, interval=-1, down_time=0.01):
        self.task.send_key(self.task.key_config.get('Resonance Key'), interval=interval, down_time=down_time)
        self.sleep(post_sleep)

    def update_res_cd(self):
        current = time.time()
        if current - self.last_res > self.res_cd:  # count the first click only
            self.last_res = time.time()

    def update_echo_cd(self):
        current = time.time()
        if current - self.last_echo > self.echo_cd:  # count the first click only
            self.last_echo = time.time()

    def click_echo(self, duration=0, sleep_time=0):
        self.logger.debug(f'click_echo start duration: {duration}')
        if self.has_cd('echo'):
            self.logger.debug('click_echo has cd return ')
            return False
        clicked = False
        start = time.time()
        last_click = 0
        while True:
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
                self.task.send_key(self.get_echo_key())
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
        self.logger.info('reset state')
        self.has_intro = False

    def click_liberation(self, wait_end=True, con_less_than=-1, send_click=False):
        if con_less_than > 0:
            if self.get_current_con() > con_less_than:
                return False
        self.logger.debug(f'click_liberation start')
        start = time.time()
        last_click = 0
        clicked = False
        while self.liberation_available():  # clicked and still in team wait for animation
            self.logger.debug(f'click_liberation liberation_available click')
            now = time.time()
            if now - last_click > 0.1:
                self.task.send_key(self.get_liberation_key())
                self.liberation_available_mark = False
                clicked = True
                last_click = now
            if time.time() - start > 5:
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
            clicked = True
            if send_click:
                self.task.click(interval=0.1)
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

    def add_freeze_duration(self, start, duration, freeze_time=0):
        if duration > freeze_time:
            current_time = time.time()
            self.freeze_durations = [item for item in self.freeze_durations if item[0] <= current_time - 15]
            self.freeze_durations.append((start, duration, freeze_time))

    def time_elapsed_accounting_for_freeze(self, start):
        to_minus = 0
        for freeze_start, duration, freeze_time in self.freeze_durations:
            if start < freeze_start:
                to_minus += duration - freeze_time
        return time.time() - start - to_minus

    def get_liberation_key(self):
        return self.task.key_config['Liberation Key']

    def get_echo_key(self):
        return self.task.key_config['Echo Key']

    def get_resonance_key(self):
        return self.task.key_config['Resonance Key']

    def get_switch_priority(self, current_char, has_intro):
        priority = self.do_get_switch_priority(current_char, has_intro)
        if priority < Priority.MAX and time.time() - self.last_switch_time < 0.9:
            return Priority.SWITCH_CD  # switch cd
        else:
            return priority

    def do_get_switch_priority(self, current_char, has_intro=False):
        priority = 0
        if self.count_liberation_priority() and self.liberation_available():
            priority += self.count_liberation_priority()
        if self.count_resonance_priority() and self.resonance_available():
            priority += self.count_resonance_priority()
        if self.count_forte_priority() and self._is_forte_full:
            priority += self.count_forte_priority()
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

    def resonance_available(self, current=None, check_ready=False):
        if self.is_current_char:
            snap = self.current_resonance() if current is None else current
            if check_ready and snap == 0:
                return False
            return self.is_available(snap, 'resonance')
        elif self.res_cd > 0:
            return time.time() - self.last_res > self.res_cd

    def echo_available(self, current=None):
        if self.is_current_char:
            snap = self.current_echo() if current is None else current
            return self.is_available(snap, 'echo')
        elif self.echo_cd > 0:
            return time.time() - self.last_echo > self.echo_cd

    def is_con_full(self):
        return self.get_current_con() == 1

    def get_current_con(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1422, 1939, to_x=1566, to_y=2076, name='con_full',
                                             hcenter=True)
        box.confidence = 0

        max_area = 0
        percent = 0
        max_is_full = False
        color_index = -1
        target_index = self.config.get('_ring_color_index', -1)
        cropped = box.crop_frame(self.task.frame)
        for i in range(len(con_colors)):
            if target_index != -1 and i != target_index:
                continue
            color_range = con_colors[i]
            area, is_full = self.count_rings(cropped, color_range,
                                             1500 / 3840 / 2160 * self.task.screen_width * self.task.screen_height)
            # self.logger.debug(f'is_con_full test color_range {color_range} {area, is_full}')
            if is_full:
                max_is_full = is_full
                color_index = i
            if area > max_area:
                max_area = int(area)
        if max_is_full:
            self.logger.info(
                f'is_con_full found a full ring {self.config.get("_full_ring_area", 0)} -> {max_area}  {color_index}')
            self.config['_full_ring_area'] = max_area
            self.config['_ring_color_index'] = color_index
            self.logger.info(
                f'is_con_full2 found a full ring {self.config.get("_full_ring_area", 0)} -> {max_area}  {color_index}')
        if self.config.get('_full_ring_area', 0) > 0:
            percent = max_area / self.config['_full_ring_area']
        if not max_is_full and percent >= 1:
            self.logger.warning(
                f'is_con_full not full but percent greater than 1, set to 0.99, {percent} {max_is_full}')
            # self.task.screenshot(
            #     f'is_con_full not full but percent greater than 1, set to 0.99, {percent} {max_is_full}',
            #     cropped)
            percent = 0.99
        if percent > 1:
            self.logger.error(f'is_con_full percent greater than 1, set to 1, {percent} {max_is_full}')
            self.task.screenshot(f'is_con_full percent greater than 1, set to 1, {percent} {max_is_full}', cropped)
            percent = 1
        # self.logger.info(
        #     f'is_con_full {self} {percent} {max_area}/{self.config.get("_full_ring_area", 0)} {color_index} ')
        # if self.task.debug:
        #     self.task.screenshot(
        #         f'is_con_full {self} {percent} {max_area}/{self.config.get("_full_ring_area", 0)} {color_index} ',
        #         cropped)
        box.confidence = percent
        self.current_con = percent
        self.task.draw_boxes(f'is_con_full_{self}', box)
        if percent > 1:
            percent = 1
        return percent

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
        self.logger.debug(f'is_forte_full {white_percent}')
        box.confidence = white_percent
        self.task.draw_boxes('forte_full', box)
        self._is_forte_full = white_percent > 0.08
        return self._is_forte_full

    def liberation_available(self):
        if self.liberation_available_mark:
            return True
        if self.is_current_char:
            snap = self.current_liberation()
            if snap == 0:
                return False
            else:
                return self.is_available(snap, 'liberation')
        # else:
        #     mark_to_check = char_lib_check_marks[self.index]
        #     box = self.task.get_box_by_name(mark_to_check)
        #     box = box.copy(x_offset=-box.width, y_offset=-box.height, width_offset=box.width * 2,
        #                    height_offset=box.height * 2)
        #     for match in char_lib_check_marks:
        #         mark = self.task.find_one(match, box=box, canny_lower=10, canny_higher=80, threshold=0.8)
        #         if mark is not None:
        #             self.logger.debug(f'{self.__repr__()} liberation ready by checking mark {mark}')
        #             self.liberation_available_mark = True
        #             return True

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

    def count_rings(self, image, color_range, min_area):
        # Define the color range
        lower_bound, upper_bound = color_range_to_bound(color_range)

        image_with_contours = image.copy()

        # Create a binary mask
        mask = cv2.inRange(image, lower_bound, upper_bound)

        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        colors = [
            (0, 255, 0),  # Green
            (0, 0, 255),  # Red
            (255, 0, 0),  # Blue
            (0, 255, 255),  # Yellow
            (255, 0, 255),  # Magenta
            (255, 255, 0)  # Cyan
        ]

        # Function to check if a component forms a ring
        def is_full_ring(component_mask):
            # Find contours
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours) != 1:
                return False
            contour = contours[0]

            # Check if the contour is closed by checking if the start and end points are the same
            # if cv2.arcLength(contour, True) > 0:
            #     return True
            # Approximate the contour with polygons.
            epsilon = 0.05 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Check if the polygon is closed (has no gaps) and has a reasonable number of vertices for a ring.
            if not cv2.isContourConvex(approx) or len(approx) < 4:
                return False

            # All conditions met, likely a close ring.
            return True

        # Iterate over each component
        ring_count = 0
        is_full = False
        the_area = 0
        for label in range(1, num_labels):
            x, y, width, height, area = stats[label, :5]
            bounding_box_area = width * height
            component_mask = (labels == label).astype(np.uint8) * 255
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            color = colors[label % len(colors)]
            cv2.drawContours(image_with_contours, contours, -1, color, 2)
            if bounding_box_area >= min_area:
                # Select a color from the list based on the label index
                if is_full_ring(component_mask):
                    is_full = True
                the_area = area
                ring_count += 1

        # if self.task.debug:
        # Save or display the image with contours
        # cv2.imwrite(f'test\\test_{self}_{is_full}_{the_area}_{lower_bound}.jpg', image_with_contours)
        if ring_count > 1:
            is_full = False
            the_area = 0
            self.logger.warning(f'is_con_full found multiple rings {ring_count}')

        return the_area, is_full


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

con_colors = [
    {
        'r': (205, 235),
        'g': (190, 222),  # for yellow spectro
        'b': (90, 130)
    },
    {
        'r': (150, 190),  # Red range
        'g': (95, 140),  # Green range for purple electric
        'b': (210, 249)  # Blue range
    },
    {
        'r': (200, 230),  # Red range
        'g': (100, 130),  # Green range    for red fire
        'b': (75, 105)  # Blue range
    },
    {
        'r': (60, 95),  # Red range
        'g': (150, 180),  # Green range    for blue ice
        'b': (210, 245)  # Blue range
    },
    {
        'r': (70, 110),  # Red range
        'g': (215, 250),  # Green range    for green wind
        'b': (155, 190)  # Blue range
    },
    {
        'r': (190, 220),  # Red range
        'g': (65, 105),  # Green range    for havoc
        'b': (145, 175)  # Blue range
    }
]
