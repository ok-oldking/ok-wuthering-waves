from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        self.click_liberation()
        if self.click_resonance()[0]:
            return self.switch_next_char()
        if self.click_echo():
            return self.switch_next_char()

        self.heavy_attack(0.75)
        self.sleep(0.4)
        self.switch_next_char()
