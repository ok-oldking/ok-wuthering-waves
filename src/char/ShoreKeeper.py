from src.char.BaseChar import BaseChar

class ShoreKeeper(BaseChar):
    def do_perform(self):
        if self.liberation_available():
            self.click_liberation()
        if self.resonance_available():
            self.click_resonance(send_click=False)
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        self.switch_next_char()
