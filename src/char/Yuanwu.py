from src.char.BaseChar import BaseChar


class Yuanwu(BaseChar):

    def count_resonance_priority(self):
        return 0

    def count_echo_priority(self):
        return 0

    def count_base_priority(self):
        return -1

    def do_perform(self):
        self.click_liberation(con_less_than=1)
        if self.is_forte_full():
            self.send_resonance_key(down_time=0.6, post_sleep=0.2)
        elif self.click_echo():
            pass
        else:
            self.continues_normal_attack(0.2)
        self.switch_next_char()
