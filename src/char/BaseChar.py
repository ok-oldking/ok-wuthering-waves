import time
from enum import IntEnum

from ok.color.Color import white_color, calculate_colorfulness
from ok.logging.Logger import get_logger
from src.task.AutoCombatTask import AutoCombatTask


class Priority(IntEnum):
    SWITCH_CD = -1000
    SKILL_AVAILABLE = 100
    ALL_IN_CD = 0
    NORMAL = 10


char_lib_check_marks = ['char_1_lib_check_mark', 'char_2_lib_check_mark', 'char_3_lib_check_mark']

logger = get_logger(__name__)


class BaseChar:
    def __init__(self, task: AutoCombatTask, index, res_cd=0):
        self.white_off_threshold = 0.002
        self.task = task
        self.sleep_adjust = 0.001
        self.index = index
        self.base_resonance_white_percentage = 0
        self.base_echo_white_percentage = 0
        self.base_liberation_white_percentage = 0
        self.last_switch_time = -1
        self.last_res = -1
        self.has_intro = False
        self.res_cd = res_cd
        self.con_ready = False
        self.is_current_char = False

    def perform(self):
        self.is_current_char = True
        self.do_perform()
        logger.debug(f'set current char false {self.index}')
        self.is_current_char = False

    def do_perform(self):
        if self.liberation_available():
            self.click_liberation()
            self.sleep(1.5)
        if self.resonance_available():
            self.click_resonance()
            self.sleep(0.1)
        elif self.echo_available():
            self.click_echo()
            self.sleep(0.5)
        self.switch_next_char()
        self.con_ready = False

    def __repr__(self):
        return self.__class__.__name__

    def switch_next_char(self, post_action=None):
        self.last_switch_time = self.task.switch_next_char(self, post_action=post_action)

    def sleep(self, sec):
        self.task.sleep(sec + self.sleep_adjust)

    def click_resonance(self):
        self.task.send_key('e')

    def update_res_cd(self):
        current = time.time()
        if current - self.last_res > self.res_cd:  # count the first click only
            self.last_res = time.time()

    def click_echo(self):
        self.task.send_key(self.get_echo_key())

    def click_liberation(self):
        self.task.send_key(self.get_liberation_key())

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
        if priority > 0:
            priority += Priority.SKILL_AVAILABLE
        return priority

    def resonance_available(self):
        if self.is_current_char:
            snap1 = self.current_resonance()
            if snap1 == 0:
                return False
            if self.base_resonance_white_percentage != 0:
                return abs(self.base_resonance_white_percentage - snap1) < self.white_off_threshold
            cd_text = self.task.ocr(box=self.task.get_box_by_name('box_resonance'), target_height=540)
            if not cd_text:
                self.base_resonance_white_percentage = snap1
                logger.info(f'set base resonance to {self.base_resonance_white_percentage:.3f}')
                return True
        else:
            if self.res_cd > 0:
                return time.time() - self.last_res > self.res_cd

    def echo_available(self):
        snap1 = self.current_echo()
        if snap1 == 0:
            return False
        if self.base_echo_white_percentage != 0:
            return abs(self.base_echo_white_percentage - snap1) < self.white_off_threshold
        cd_text = self.task.ocr(box=self.task.get_box_by_name('box_echo'), target_height=540)
        if not cd_text:
            self.base_echo_white_percentage = snap1
            logger.info(f'set base resonance to {self.base_echo_white_percentage:.3f}')
            return True

    def is_con_full(self):
        box = self.task.box_of_screen(1540 / 3840, 2007 / 2160, 1545 / 3840, 2010 / 2160, name='con_full')
        colorfulness = calculate_colorfulness(self.task.frame, box)
        box.confidence = colorfulness
        self.task.draw_boxes('con_full', box)
        if colorfulness > 0.1:
            return True

    def is_forte_full(self):
        box = self.task.box_of_screen(2170 / 3840, 1998 / 2160, 2174 / 3840, 2007 / 2160, name='forte_full')
        colorfulness = calculate_colorfulness(self.task.frame, box)
        box.confidence = colorfulness
        self.task.draw_boxes('forte_full', box)
        if colorfulness > 0.1:
            return True

    def liberation_available(self):
        if self.is_current_char:
            snap1_lib = self.current_liberation()
            if snap1_lib == 0:
                return False
            if self.base_liberation_white_percentage != 0:
                return abs(self.base_liberation_white_percentage - snap1_lib) < self.white_off_threshold
            cd_text = self.task.ocr(box=self.task.get_box_by_name('box_liberation'), target_height=540)
            if not cd_text:
                self.base_liberation_white_percentage = snap1_lib
                logger.info(f'{self} set base liberation to {self.base_liberation_white_percentage:.3f}')
                return True
            else:
                logger.debug(
                    f'{self} set base liberation {snap1_lib:.3f} has text {cd_text}')
        else:
            mark_to_check = char_lib_check_marks[self.index]
            mark = self.task.find_one(mark_to_check, use_gray_scale=True)
            if mark is not None:
                logger.debug(f'{self.__repr__()} liberation ready by checking mark')
                return True

    def __str__(self):
        return self.__repr__()

    def normal_attack(self):
        self.task.click()

    def heavy_attack(self):
        self.task.mouse_down()
        self.sleep(0.6)
        self.task.mouse_up()

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
