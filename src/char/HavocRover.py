from src.char.BaseChar import BaseChar


class HavocRover(BaseChar):
    def do_perform(self):
        if self.is_forte_full() and self.liberation_available():
            self.heavy_attack()
        if self.liberation_available():
            self.click_liberation()
            self.sleep(2)
        if self.resonance_available():
            self.click_resonance()
        if self.echo_available():
            self.sleep(0.3)
            self.click_echo()
            self.sleep(0.3)
        self.switch_next_char()
