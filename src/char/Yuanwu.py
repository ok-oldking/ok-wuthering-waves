from src.char.BaseChar import BaseChar


class Yuanwu(BaseChar):

    def count_resonance_priority(self):
        return 0

    def count_echo_priority(self):
        return 0

    def count_base_priority(self):
        return -2

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)
            return self.switch_next_char()
        self.click_liberation(con_less_than=1)
        if self.is_forte_full():
            self.heavy_attack()
        self.click_resonance()
        self.normal_attack()
        self.click_echo()
        self.switch_next_char()
