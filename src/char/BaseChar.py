import time
from enum import IntEnum, StrEnum

from ok.color.Color import white_color, calculate_colorfulness
from ok.logging.Logger import get_logger


class Priority(IntEnum):
    MIN = -999999999
    SWITCH_CD = -1000
    CURRENT_CHAR = -100
    SKILL_AVAILABLE = 100
    ALL_IN_CD = 0
    NORMAL = 10


class Role(StrEnum):
    DEFAULT = 'Default'
    SUB_DPS = 'Sub DPS'
    MAIN_DPS = 'Main DPS'
    HEALER = 'Healer'


role_values = [role for role in Role]

char_lib_check_marks = ['char_1_lib_check_mark', 'char_2_lib_check_mark', 'char_3_lib_check_mark']

logger = get_logger(__name__)


class BaseChar:

    def __init__(self, task, index, res_cd=0):
        self.white_off_threshold = 0.01
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
        self.is_current_char = False

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
        logger.debug(f'set current char false {self.index}')

    def wait_down(self):
        start = time.time()
        while self.flying():
            self.task.click()
            self.sleep(0.05)

        self.task.screenshot(
            f'{self}_down_finish_{(time.time() - start):.2f}_f:{self.is_forte_full()}_e:{self.resonance_available()}_r:{self.echo_available()}_q:{self.liberation_available()}_i{self.has_intro}')

    def do_perform(self):
        self.click_liberation()
        if self.resonance_available():
            self.click_resonance()
            self.sleep(0.1)
        if self.echo_available():
            self.click_echo()
            self.sleep(0.1)
        self.switch_next_char()

    def __repr__(self):
        return self.__class__.__name__ + ('_T' if self.is_current_char else '_F')

    def switch_next_char(self, post_action=None):
        self.last_switch_time = self.task.switch_next_char(self, post_action=post_action)

    def sleep(self, sec):
        self.task.sleep_check_combat(sec + self.sleep_adjust)

    def click_resonance(self):
        self.check_combat()
        self.task.send_key(self.task.config.get('Resonance Key'))
        while True:
            curren_resonance = self.current_resonance()
            if curren_resonance > 0 and abs(
                    curren_resonance - self.base_resonance_white_percentage) > self.white_off_threshold:
                break
            self.sleep(0.02)
            self.task.click()
            self.sleep(0.02)
            self.task.send_key(self.task.config.get('Resonance Key'))
        logger.info(f'{self} click resonance')

    def update_res_cd(self):
        current = time.time()
        if current - self.last_res > self.res_cd:  # count the first click only
            self.last_res = time.time()

    def click_echo(self):
        self.check_combat()
        self.task.send_key(self.get_echo_key())
        while True:
            current_echo = self.current_echo()
            if current_echo > 0 and abs(
                    current_echo - self.base_echo_white_percentage) > self.white_off_threshold:
                break
            self.sleep(0.05)
            self.task.send_key(self.get_echo_key())
        logger.info(f'{self} click echo')

    def check_combat(self):
        self.task.check_combat()

    def click_liberation(self, wait_end=True):
        logger.info(f'click_liberation {self}')
        self.check_combat()
        self.task.in_liberation = True
        self.task.send_key(self.get_liberation_key())
        while self.liberation_available():
            self.sleep(0.02)
            self.task.send_key(self.get_liberation_key())
        start = time.time()
        while not self.task.in_team()[0]:
            if start - time.time() > 5:
                logger.info('too long a liberation, the boss was killed by the liberation')
                self.task.reset_to_false()
                from src.task.BaseCombatTask import NotInCombatException
                raise NotInCombatException('not in combat')
            self.sleep(0.02)
        self.task.in_liberation = False
        self.task.info[f'{self} liberation time'] = f'{(time.time() - start):.2f}'

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

    def resonance_available(self):
        if self.is_current_char:
            snap1 = self.current_resonance()
            if snap1 == 0:
                return False
            if self.base_resonance_white_percentage != 0:
                return abs(self.base_resonance_white_percentage - snap1) < self.white_off_threshold
            cd_text = self.task.ocr(box=self.task.get_box_by_name('box_resonance'), target_height=540, threshold=0.95)
            if len(cd_text) == 0 or not is_float(cd_text[0].name):
                self.base_resonance_white_percentage = snap1
                if self.task.debug:
                    self.task.screenshot(f'{self}_resonance_{snap1:.3f}')
                logger.info(f'{self} set base resonance to {self.base_resonance_white_percentage:.3f}')
                return True
            if cd_text:
                logger.info(f'{self} set base resonance to has text {cd_text}')
        else:
            if self.res_cd > 0:
                return time.time() - self.last_res > self.res_cd

    def echo_available(self):
        snap1 = self.current_echo()
        if snap1 == 0:
            return False
        if self.base_echo_white_percentage != 0:
            return abs(self.base_echo_white_percentage - snap1) < self.white_off_threshold
        cd_text = self.task.ocr(box=self.task.get_box_by_name('box_echo'), target_height=540, threshold=0.95)
        if not cd_text or not is_float(cd_text[0].name):
            self.base_echo_white_percentage = snap1
            if self.task.debug:
                self.task.screenshot(f'{self}_echo_{snap1:.3f}')
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
        box = self.task.box_of_screen(2251 / 3840, 1993 / 2160, 2271 / 3840, 2016 / 2160, name='forte_full')
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        box.confidence = white_percent
        self.task.draw_boxes('forte_full', box)
        if white_percent > 0.2:
            return True

    def liberation_available(self):
        if self.is_current_char:
            snap1_lib = self.current_liberation()
            if snap1_lib == 0:
                return False
            if self.base_liberation_white_percentage != 0:
                return abs(self.base_liberation_white_percentage - snap1_lib) < self.white_off_threshold
            cd_text = self.task.ocr(box=self.task.get_box_by_name('box_liberation'), target_height=540, threshold=0.95)
            if not cd_text or not is_float(cd_text[0].name):
                self.base_liberation_white_percentage = snap1_lib
                logger.info(f'{self} set base liberation to {self.base_liberation_white_percentage:.3f}')
                if self.task.debug:
                    self.task.screenshot(f'{self}_liberation_{self.base_liberation_white_percentage:.3f}')
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
        self.check_combat()
        self.task.click()

    def heavy_attack(self):
        self.check_combat()
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
        return self.get_current_levitator() == 0

    def get_current_levitator(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('edge_levitator'))


forte_white_color = {
    'r': (244, 255),  # Red range
    'g': (246, 255),  # Green range
    'b': (250, 255)  # Blue range
}


def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
