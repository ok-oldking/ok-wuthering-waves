from src.char.BaseChar import BaseChar


class Yuanwu(BaseChar):

    def do_perform(self):
        if self.click_liberation(con_less_than=1):
            self.click_resonance()
            return self.switch_next_char()
        if self.has_intro:
            self.continues_normal_attack(1.2)
            return self.switch_next_char()
        self.click_resonance()
        self.click_echo()
        self.switch_next_char()
