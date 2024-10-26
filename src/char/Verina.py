from src.char.BaseChar import BaseChar

class Verina(BaseChar):

    def do_perform(self):
        self.click_liberation()
        if self.flying():
            self.normal_attack()
            return self.switch_next_char()
        if not self.is_con_full():
            self.click_resonance()
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        self.switch_next_char()
