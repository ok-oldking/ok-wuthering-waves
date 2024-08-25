from src.char.BaseChar import BaseChar


class Yuanwu(BaseChar):

    def count_resonance_priority(self):
        return 0

    def count_echo_priority(self):
        return 0

    def count_base_priority(self):
        return -1

    def do_perform(self):
        if self.click_liberation(con_less_than=1):
            return self.switch_next_char()
        if self.has_intro:
            self.continues_normal_attack(1.2)
        if self.is_forte_full():
            self.send_resonance_key(down_time=0.7, post_sleep=0.2)
            return self.switch_next_char()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_perform),
                                     until_con_full=True)
        if self.get_current_con() > 0.65:
            self.click_echo()
        self.switch_next_char()
