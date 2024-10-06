from src.char.Healer import Healer


class ShoreKeeper(Healer):

    def do_perform(self):
        self.click_liberation()
        self.click_resonance(send_click=False)
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        self.switch_next_char()
