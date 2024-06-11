from src.char.BaseChar import BaseChar


class Verina(BaseChar):

    def perform(self):
        if self.liberation_available():
            self.click_liberation()
            self.sleep(1.5)
        if self.resonance_available():
            self.click_resonance()
            if self.echo_available():
                self.sleep(0.3)
                self.click_echo()
            self.sleep(0.3)
        else:
            self.heavy_attack()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char, has_intro=False):
        if has_intro:
            return -3
        else:
            return 2
