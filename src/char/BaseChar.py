import time
from enum import IntEnum, StrEnum

from ok.color.Color import white_color, calculate_colorfulness, get_connected_area_by_color
from ok.logging.Logger import get_logger


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

    def __init__(self, task, index, res_cd=0, echo_cd=0):
        self.white_off_threshold = 0.01
        self.echo_cd = echo_cd
        self.task = task
        self.sleep_adjust = 0.001
        self.index = index
        self.base_resonance_white_percentage = 0
        self.base_echo_white_percentage = 0
        self.base_liberation_white_percentage = 0
        self.last_switch_time = -1
        self.last_res = -1
        self.last_echo = -1
        self.has_intro = False
        self.res_cd = res_cd
        self.is_current_char = False
        self.liberation_available_mark = False
        self.logger = get_logger(self.name)

    @property
    def name(self):
        return self.__class__.__name__

    def __eq__(self, other):
        if isinstance(other, BaseChar):
            return self.name == other.name
        return False

    def perform(self):
        # self.wait_down()
        self.do_perform()
        self.logger.debug(f'set current char false {self.index}')

    def wait_down(self):
        start = time.time()
        while self.flying():
            self.task.click()
            self.sleep(0.2)

        self.task.screenshot(
            f'{self}_down_finish_{(time.time() - start):.2f}_f:{self.is_forte_full()}_e:{self.resonance_available()}_r:{self.echo_available()}_q:{self.liberation_available()}_i{self.has_intro}')

    def do_perform(self):
        self.click_liberation()
        if self.click_resonance()[0]:
            return self.switch_next_char()
        if self.click_echo():
            return self.switch_next_char()
        self.switch_next_char()

    def is_available(self, percent, box_name):
        if percent == 0:
            return True

        box = self.task.get_box_by_name(f'box_{box_name}')
        num_labels, stats = get_connected_area_by_color(box.crop_frame(self.task.frame), dot_color, connectivity=8)
        big_area_count = 0
        has_dot = False
        number_count = 0
        for i in range(1, num_labels):
            # Check if the connected component touches the border
            left, top, width, height, area = stats[i]
            if area / self.task.frame.shape[0] / self.task.frame.shape[
                1] > 20 / 3840 / 2160:
                big_area_count += 1
            if left > 0 and top > 0 and left + width < box.width and top + height < box.height:
                self.logger.debug(f"{box_name} Area of connected component {i}: {area} pixels {width}x{height}")
                if 20 / 3840 / 2160 <= area / self.task.frame.shape[0] / self.task.frame.shape[
                    1] <= 60 / 3840 / 2160 and abs(width - height) / (width + height) < 0.1:
                    has_dot = True
                elif 150 / 3840 / 2160 <= area / self.task.frame.shape[0] / self.task.frame.shape[
                    1] <= 500 / 3840 / 2160:
                    number_count += 1
        self.logger.debug(f"{box_name} number_count {number_count} big_count {big_area_count} has_dot {has_dot}")
        if big_area_count > 5:
            return True
        return not (has_dot and 2 <= number_count <= 3)

        # # dot = self.task.find_one('edge_echo_cd_dot', box=box, canny_lower=40, canny_higher=80, threshold=0.5)
        #
        # if dot is None:
        #     self.logger.debug(f'find dot not exist cost : {time.time() - start}')
        #     return True
        # else:
        #     self.logger.debug(f'find dot exist cost : {time.time() - start} {dot}')
        #     return False

    def __repr__(self):
        return self.__class__.__name__ + ('_T' if self.is_current_char else '_F')

    def switch_next_char(self, post_action=None):
        self.liberation_available_mark = self.liberation_available()
        self.last_switch_time = self.task.switch_next_char(self, post_action=post_action)

    def sleep(self, sec):
        if sec > 0:
            self.task.sleep_check_combat(sec + self.sleep_adjust)

    def click_resonance(self, post_sleep=0, has_animation=False):
        clicked = None
        self.logger.debug(f'click_resonance start')
        last_click = 0
        last_op = 'click'
        resonance_click_time = 0
        animated = False
        while True:
            if has_animation:
                if not self.task.in_team()[0]:
                    animated = True
                    if time.time() - resonance_click_time > 6:
                        self.logger.error(f'resonance animation too long, breaking')
                        self.check_combat()
                self.task.next_frame()
            else:
                self.check_combat()
            current_resonance = self.current_resonance()
            if not self.resonance_available(current_resonance):
                break
            self.logger.debug(f'click_resonance resonance_available click')
            now = time.time()
            if now - last_click > 0.1:
                if current_resonance == 0 or last_op != 'click':
                    self.task.click()
                    last_op = 'click'
                else:
                    if resonance_click_time == 0:
                        clicked = True
                        resonance_click_time = now
                    last_op = 'resonance'
                    self.update_res_cd()
                    self.send_resonance_key()
                last_click = now
            self.task.next_frame()
        if clicked:
            self.sleep(post_sleep)
        self.logger.debug(f'click_resonance end')
        duration = time.time() - resonance_click_time if resonance_click_time != 0 else 0
        return clicked, duration, animated

    def send_resonance_key(self, post_sleep=0, interval=-1):
        self.task.send_key(self.task.config.get('Resonance Key'), interval=interval)
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
        self.logger.debug(f'click_echo start')
        clicked = False
        start = 0
        last_click = 0
        while True:
            self.check_combat()
            current = self.current_echo()
            if duration == 0 and not self.echo_available(current):
                break
            now = time.time()
            if duration > 0 and start != 0:
                if now - start > duration:
                    break
            self.logger.debug(f'click_echo echo_available click')
            if now - last_click > 0.1:
                if current == 0:
                    self.task.click()
                else:
                    if start == 0:
                        start = now
                    clicked = True
                    self.update_echo_cd()
                    self.task.send_key(self.get_echo_key())
                    last_click = now
            self.task.next_frame()
        self.logger.debug(f'click_echo end {clicked}')
        return clicked

    def check_combat(self):
        self.task.check_combat()

    def click_liberation(self, wait_end=True):
        self.logger.debug(f'click_liberation start')
        start = time.time()
        last_click = 0
        while self.liberation_available():
            self.check_combat()
            self.logger.debug(f'click_liberation liberation_available click')
            now = time.time()
            if now - last_click > 0.1:
                self.task.send_key(self.get_liberation_key())
                self.task.in_liberation = True
                self.liberation_available_mark = False
                last_click = now
            if time.time() - start > 5:
                self.task.raise_not_in_combat('too long clicking a liberation')
            self.task.next_frame()
        while self.task.in_liberation and not self.task.in_team()[0]:
            if time.time() - start > 5:
                self.task.raise_not_in_combat('too long a liberation, the boss was killed by the liberation')
            self.task.next_frame()
        self.task.in_liberation = False
        if last_click != 0:
            liberation_time = f'{(time.time() - start):.2f}'
            self.task.info[f'{self} liberation time'] = liberation_time
            self.logger.debug(f'click_liberation end {liberation_time}')
        return last_click != 0

    def get_liberation_key(self):
        return self.task.config['Liberation Key']

    def get_echo_key(self):
        return self.task.config['Echo Key']

    def get_switch_priority(self, current_char, has_intro):
        if time.time() - self.last_switch_time < 1:
            return Priority.SWITCH_CD  # switch cd
        else:
            return self.do_get_switch_priority(current_char, has_intro)

    def do_get_switch_priority(self, current_char, has_intro=False):
        priority = 0
        if self.liberation_available():
            priority += 1
        if self.resonance_available():
            priority += 1
        if self.is_forte_full():
            priority += 1
        if priority > 0:
            priority += Priority.SKILL_AVAILABLE
        return priority

    def resonance_available(self, current=None):
        if self.is_current_char:
            snap = self.current_resonance() if current is None else current
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
        box = self.task.box_of_screen(1540 / 3840, 2007 / 2160, 1545 / 3840, 2010 / 2160, name='con_full')
        colorfulness = calculate_colorfulness(self.task.frame, box)
        box.confidence = colorfulness
        self.task.draw_boxes('con_full', box)
        if colorfulness > 0.1:
            return True

    def is_forte_full(self):
        box = self.task.box_of_screen(2251 / 3840, 1993 / 2160, 2271 / 3840, 2016 / 2160, name='forte_full')
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        box.confidence = white_percent
        self.task.draw_boxes('forte_full', box)
        if white_percent > 0.2:
            return True

    def liberation_available(self):
        if self.liberation_available_mark:
            return True
        if self.is_current_char:
            snap = self.current_liberation()
            if snap == 0:
                return False
            else:
                return self.is_available(snap, 'liberation')
        else:
            mark_to_check = char_lib_check_marks[self.index]
            box = self.task.get_box_by_name(mark_to_check)
            box = box.copy(x_offset=-box.width, y_offset=-box.height, width_offset=box.width * 2,
                           height_offset=box.height * 2)
            for match in char_lib_check_marks:
                mark = self.task.find_one(match, box=box, canny_lower=10, canny_higher=80, threshold=0.6)
                if mark is not None:
                    self.logger.debug(f'{self.__repr__()} liberation ready by checking mark {mark}')
                    self.liberation_available_mark = True
                    return True

    def __str__(self):
        return self.__repr__()

    def continues_normal_attack(self, duration, interval=0.2):
        start = time.time()
        while time.time() - start < duration:
            self.normal_attack()
            self.sleep(interval)

    def normal_attack(self):
        self.logger.debug('normal attack')
        self.check_combat()
        self.task.click()

    def heavy_attack(self):
        self.check_combat()
        self.logger.debug('heavy attack start')
        self.task.mouse_down()
        self.sleep(0.6)
        self.task.mouse_up()
        self.logger.debug('heavy attack end')

    def current_resonance(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('box_resonance'))

    def current_echo(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('box_echo'))

    def current_liberation(self):
        return self.task.calculate_color_percentage(white_color, self.task.get_box_by_name('box_liberation'))

    def flying(self):
        return self.current_resonance() == 0

    def get_current_levitator(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('edge_levitator'))


forte_white_color = {
    'r': (244, 255),  # Red range
    'g': (246, 255),  # Green range
    'b': (250, 255)  # Blue range
}

dot_color = {
    'r': (250, 255),  # Red range
    'g': (250, 255),  # Green range
    'b': (250, 255)  # Blue range
}
