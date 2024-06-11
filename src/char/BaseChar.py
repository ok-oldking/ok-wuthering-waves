import time

from ok.color.Color import white_color
from src.task.AutoCombatTask import AutoCombatTask


class BaseChar:
    def __init__(self, task: AutoCombatTask, index):
        self.white_off_threshold = 0.001
        self.task = task
        self.sleep_adjust = 0.001
        self.index = index
        self.base_resonance_white_percentage = self.current_resonance()
        self.base_echo_white_percentage = self.current_echo()
        self.base_liberation_white_percentage = 0
        self.last_switch_time = time.time()

    def perform(self):
        if self.resonance_available():
            self.click_resonance()
            if self.echo_available():
                self.sleep(0.3)
                self.click_echo()
            self.sleep(0.3)
        elif self.liberation_available():
            self.click_liberation()
            self.sleep(1.5)
        self.switch_next_char()

    def __repr__(self):
        return self.__class__.__name__

    def switch_next_char(self, post_action=None):
        self.last_switch_time = time.time()
        self.task.switch_next_char(self, post_action=post_action)

    def sleep(self, time):
        self.task.sleep(time + self.sleep_adjust)

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

    def get_switch_priority(self, current_char):
        if time.time() - self.last_switch_time < 1:
            return -2  # switch cd
        else:
            return self.do_get_switch_priority(current_char)

    def do_get_switch_priority(self, current_char):
        return 1

    def resonance_available(self):
        return abs(self.base_resonance_white_percentage - self.current_resonance()) < self.white_off_threshold

    def echo_available(self):
        return abs(self.base_echo_white_percentage - self.current_echo()) < self.white_off_threshold

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

    def current_resonance(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('box_resonance'))

    def current_echo(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('box_echo'))

    def current_liberation(self):
        return self.task.calculate_color_percentage(white_color,
                                                    self.task.get_box_by_name('box_liberation'))

    def load(self, resonance_white_percentage, liberation_white_percentage):
        self.base_resonance_white_percentage = resonance_white_percentage
        self.liberation_white_percentage = liberation_white_percentage
