from src.char.BaseChar import BaseChar

class ShoreKeeper(BaseChar):
    def do_perform(self):
        self.click_liberation()
        if self.resonance_available():
            self.click_resonance(post_sleep=0.3)
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        self.switch_next_char()
