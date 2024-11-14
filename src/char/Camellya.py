import time

from src.char.BaseChar import BaseChar, Priority


class Camellya(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_heavy = 0

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        self.logger.debug(
            f'Camellya last heavy time {self.last_heavy} {self.time_elapsed_accounting_for_freeze(self.last_heavy)}')
        if self.time_elapsed_accounting_for_freeze(self.last_heavy) < 1.2:
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def wait_resonance_not_gray(self, timeout=5):
        start = time.time()
        while self.current_resonance() == 0:
            self.click()
            self.sleep(0.1)
            if time.time() - start > timeout:
                self.logger.error('wait wait_resonance_not_gray timed out')

    def do_perform(self):
        self.wait_resonance_not_gray()
        self.click_liberation()
        if self.click_echo():
            return self.switch_next_char()
        # budding_wait = self.get_current_con() > 0.6
        # self.task.screenshot('click_reso1')
        start_con = self.get_current_con()
        if self.is_con_full():
            self.handle_budding()
            return self.switch_next_char()
        elif self.click_resonance()[0]:
            # self.task.screenshot('click_reso2')
            self.sleep(0.1)
            while self.get_current_con() == start_con:
                self.click()
                self.sleep(0.15)
            self.sleep(0.1)
            self.task.next_frame()
            con_change = start_con - self.get_current_con()
            self.logger.debug(f'con_change {con_change}')
            if con_change > 0.2 or self.is_con_full():
                self.handle_budding()
            return self.switch_next_char()
        self.click(after_sleep=0.1)
        self.heavy_attack(1.1)
        self.last_heavy = time.time()
        if self.is_con_full():
            self.click_resonance()
            self.handle_budding()
        self.switch_next_char()

    def handle_budding(self):
        self.logger.info('camellya_budding start')
        # if budding_wait:
        #     # self.task.screenshot('budding_wait_1')
        #     self.sleep(0.4)
        #     # self.task.screenshot('budding_wait_2')
        # budding = False
        self.click_resonance()
        budding_start_time = time.time()
        while time.time() - budding_start_time < 4 or self.task.find_one('camellya_budding', threshold=0.7):
            self.click(after_sleep=0.2)
        self.logger.info(f'camellya_budding end')
        self.click_resonance()
