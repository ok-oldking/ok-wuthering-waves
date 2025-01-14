import time

from src.char.BaseChar import BaseChar, Priority


class Carlotta(BaseChar):
    def do_perform(self):
        self.bullet = 0
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.bullet = 1
            self.continues_normal_attack(1.2)
        if self.is_forte_full():
            self.heavy_attack()
            return self.switch_next_char()
        if self.liberation_available():
            while self.liberation_available():
                self.click_liberation()
                self.check_combat()
            self.click_echo()
            return self.switch_next_char()
        if self.resonance_available():
            if self.bullet == 0:
                self.heavy_attack()
            if self.click_resonance()[0]:
                return self.switch_next_char()
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()
        self.continues_normal_attack(0.31)
        self.switch_next_char()

    def has_long_actionbar(self):
        return True
