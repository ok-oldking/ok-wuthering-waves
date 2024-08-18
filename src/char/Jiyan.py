import time

from src.char.BaseChar import BaseChar


class Jiyan(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.logger.debug('jiyan wait intro')
            self.continues_normal_attack(duration=2.0)
            # fly check not work for jiyan
        if self.click_liberation():
            start = time.time()
            while time.time() - start < 12:
                if self.click_resonance()[0]:
                    self.task.middle_click_relative(0.5, 0.5)
                    pass
                self.normal_attack()
            self.switch_next_char()
        i = 0
        while not self.is_forte_full() and not self.is_con_full():
            if i % 4 == 0:
                self.heavy_attack()
                if self.resonance_available() or self.echo_available():
                    self.task.middle_click_relative(0.5, 0.5)
                    break
                i = 0
            self.normal_attack()
            i += 1
        if not self.is_forte_full() and self.resonance_available():
            self.click_resonance(post_sleep=1.0)
        if self.echo_available():
            self.click_echo(duration=1.0)
        self.switch_next_char()
