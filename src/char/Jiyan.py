import time
from src.char.BaseChar import BaseChar

class Jiyan(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.logger.debug('jiyan wait intro')
            self.continues_normal_attack(duration=2.0)
            # fly check not work for jiyan
        self.jiyan_liberation()
        while not self.is_forte_full() and not self.is_con_full():
            self.normal_attack()  
            if self.resonance_available() or self.echo_available():
                self.task.middle_click_relative(0.5, 0.5)
                break
        if not self.is_forte_full() and self.resonance_available():
            self.click_resonance(post_sleep=1.0)
        self.click_echo()
        self.jiyan_liberation()
        self.switch_next_char()
    def jiyan_liberation(self):
        if self.liberation_available():
            if not self.is_forte_full():
                self.continues_normal_attack(2.0)
            if self.click_liberation():
                start = time.time()
                while time.time() - start < 12:
                    if self.click_resonance(post_sleep=0.5)[0]:
                        self.task.middle_click_relative(0.5, 0.5)
                    self.normal_attack()
