import time

from src.char.BaseChar import BaseChar, Priority


class Carlotta(BaseChar):

    def do_perform(self):
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.continues_normal_attack(1.2, click_resonance_if_ready_and_return=True)
        while self.click_liberation(con_less_than=1):
            continue
        if self.click_resonance()[0]:
            return self.switch_next_char()
        if self.is_forte_full():
            self.heavy_attack(0.6)
            return self.switch_next_char()
        if self.click_echo():
            return self.switch_next_char()
        self.continues_normal_attack(0.31)
        self.switch_next_char()
