import time

from src.char.BaseChar import BaseChar, Priority


class Camellya(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_heavy = 0

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            return Priority.MAX - 1
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
        self.click_liberation()
        i = 0
        start_con = self.get_current_con()
        if start_con < 0.8:
            loop_time = 1.1
        else:
            loop_time = 4.1
        budding_start_time = time.time()
        budding = False
        full = False
        while time.time() - budding_start_time < loop_time or self.task.find_one('camellya_budding', threshold=0.7):
            current_con = self.get_current_con()
            if (start_con - current_con > 0.1) and not budding:
                self.logger.info(f'confull start budding {current_con}')
                budding_start_time = time.time()
                loop_time = 5.1
                budding = True
            elif current_con == 1 and not budding and not full:
                full = True
                loop_time = 1
                budding_start_time = time.time()
            start_con = current_con
            if self.resonance_available():
                self.send_resonance_key(interval=0.1)
                if self.get_current_con() < 0.7 and not budding:
                    # self.task.screenshot(f'camellya_fast_end_{self.get_current_con()}')
                    return self.switch_next_char()
            else:
                self.click(interval=0.1)
            self.task.next_frame()
            i += 1
        if budding:
            self.click_resonance()
        self.click_echo()
        # self.task.screenshot(f'camellya_end_{self.get_current_con()}')
        self.switch_next_char()

    # def handle_budding(self):
    #     self.logger.info('camellya_budding start')
    #     budding_start_time = time.time()
    #     i = 0
    #     while time.time() - budding_start_time < 4 or self.task.find_one('camellya_budding', threshold=0.7):
    #         if self.resonance_available():
    #             self.send_resonance_key(interval=0.1)
    #             if self.current_resonance() < 0.7:
    #                 return
    #         else:
    #             self.click(interval=0.1)
    #         i += 1
    #     self.logger.info(f'camellya_budding end')
    #     self.click_resonance()
    # def switch_next_char(self, *args):
    #     self.task.screenshot(f'ca_switch_out_{self.current_con}')
    #     super().switch_next_char(*args)
