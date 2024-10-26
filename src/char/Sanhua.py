from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        self.click_liberation()
        self.click_resonance()
        self.heavy_attack(0.75)
        self.sleep(0.4)
        self.click_echo()
        self.switch_next_char()
