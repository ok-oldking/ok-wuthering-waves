import time

from ok.color.Color import white_color, calculate_colorfulness
from src.task.AutoCombatTask import AutoCombatTask


class BaseChar:
    def __init__(self, task: AutoCombatTask, index):
        self.white_off_threshold = 0.001
        self.task = task
        self.sleep_adjust = 0.001
        self.index = index
        self.base_resonance_white_percentage = 0
        self.base_echo_white_percentage = 0
        self.base_liberation_white_percentage = 0
        self.last_switch_time = time.time()
        self.has_intro = False

    def perform(self):
        if self.liberation_available():
            self.click_liberation()
            self.sleep(1.5)
        if self.resonance_available():
            self.click_resonance()
            if self.echo_available():
                self.sleep(0.3)
                self.click_echo()
            self.sleep(0.3)
        self.switch_next_char()

    def __repr__(self):
        return self.__class__.__name__

    def switch_next_char(self, post_action=None):
        self.last_switch_time = time.time()
        self.task.switch_next_char(self, post_action=post_action)

    def sleep(self, sec):
        self.task.sleep(sec + self.sleep_adjust)

    def click_resonance(self):
        self.task.send_key('e')

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
            return -1000  # switch cd
        else:
            return self.do_get_switch_priority(current_char, has_intro)

    def do_get_switch_priority(self, current_char, has_intro=False):
        return 1

    def resonance_available(self):
        snap1 = self.current_resonance()
        if snap1 == 0:
            return False
        if self.base_resonance_white_percentage != 0:
            return abs(self.base_resonance_white_percentage - snap1) < self.white_off_threshold
        self.sleep(0.2)
        snap2 = self.current_resonance()
        if snap2 == snap1:
            self.base_resonance_white_percentage = snap1
            self.task.log_info(f'set base resonance to {self.base_resonance_white_percentage:.3f}')
            return True

    def echo_available(self):
        snap1 = self.current_echo()
        if snap1 == 0:
            return False
        if self.base_echo_white_percentage != 0:
            return abs(self.base_echo_white_percentage - snap1) < self.white_off_threshold
        self.sleep(0.2)
        snap2 = self.current_echo()
        if snap2 == snap1:
            self.base_echo_white_percentage = snap1
            self.task.log_info(f'set base resonance to {self.base_echo_white_percentage:.3f}')
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
        snap1_lib = self.current_liberation()
        if snap1_lib == 0:
            return False
        if self.base_liberation_white_percentage != 0:
            return abs(self.base_liberation_white_percentage - snap1_lib) < self.white_off_threshold
        self.sleep(0.2)
        snap2_lib = self.current_liberation()
        if snap2_lib == snap1_lib:
            self.base_liberation_white_percentage = snap1_lib
            self.task.log_info(f'set base liberation to {self.base_liberation_white_percentage:.3f}')
            return True

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
