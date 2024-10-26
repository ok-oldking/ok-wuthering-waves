from src.char.BaseChar import BaseChar

class Mortefi(BaseChar):
    def do_perform(self):
        if self.liberation_available():
            self.click_liberation()
        if self.resonance_available():
            self.click_resonance()
        self.continues_normal_attack(0.7)
        if self.resonance_available():
            self.click_resonance()
        if self.echo_available():
            self.click_echo
        self.switch_next_char()
