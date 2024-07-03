from src.char.BaseChar import BaseChar


class Verina(BaseChar):

    def do_perform(self):
        self.click_liberation()
        if self.flying():
            return self.switch_next_char()
        if self.click_resonance(send_click=False)[0]:
            return self.switch_next_char()
        if self.click_echo():
            self.heavy_attack()
            return self.switch_next_char()
        # if self.current_con < 1:
        #     # self.continues_normal_attack(1.9, click_resonance_if_ready_and_return=True, until_con_full=True)
        #     if self.current_con < 1:
        self.heavy_attack()
        self.switch_next_char()

    def count_resonance_priority(self):
        return 20

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        return super().do_get_switch_priority(current_char, has_intro)
