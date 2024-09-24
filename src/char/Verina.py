from src.char.Healer import Healer


class Verina(Healer):

    def do_perform(self):
        self.click_liberation()
        if self.flying():
            self.normal_attack()
            return self.switch_next_char()
        if self.click_resonance(send_click=False)[0]:
            return self.switch_next_char()
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        # self.normal_attack()
        self.switch_next_char()
