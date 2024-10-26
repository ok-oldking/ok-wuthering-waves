from src.char.BaseChar import BaseChar

class Mortefi(BaseChar):
    def do_perform(self):
        self.click_liberation()
        if self.resonance_available():
            self.click_resonance()
        self.continues_normal_attack(0.7)
        if self.resonance_available():
            self.click_resonance()
        self.click_echo()
        self.switch_next_char()
