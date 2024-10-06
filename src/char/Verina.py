from src.char.Healer import Healer


class Verina(Healer):

    def do_perform(self):
        self.click_liberation()
        if self.flying():
            self.normal_attack()
            return self.switch_next_char()
        self.click_resonance(send_click=False)
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        self.switch_next_char()
