import time

from src.char.BaseChar import BaseChar, Priority


class Roccia(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.continues_normal_attack(1.2)
        self.click_liberation()
        start = time.time()
        if self.click_resonance()[0]:
            while self.is_forte_full() and time.time() - start < 4:
                self.click(interval=0.2)
            return self.switch_next_char()
        self.click_echo()
        self.switch_next_char()
