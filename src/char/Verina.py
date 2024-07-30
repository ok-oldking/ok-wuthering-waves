from src.char.BaseChar import BaseChar


class Verina(BaseChar):

    def do_perform(self):
        self.click_liberation()
        if self.flying():
            return self.switch_next_char()
        if self.click_resonance(send_click=False)[0]:
            return self.switch_next_char()
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        # self.normal_attack()
        self.switch_next_char()

    def count_base_priority(self):
        return - 1
