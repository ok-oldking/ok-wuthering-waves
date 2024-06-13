from src.char.BaseChar import BaseChar


class Verina(BaseChar):

    def do_perform(self):
        if self.flying():
            return self.switch_next_char()
        if self.liberation_available():
            self.click_liberation()
            self.sleep(1.5)
        if self.resonance_available():
            self.click_resonance()
            if self.echo_available():
                self.sleep(0.3)
                self.click_echo()
        self.heavy_attack()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if has_intro:
            return super().do_get_switch_priority(current_char, has_intro) - 5
        else:
            return super().do_get_switch_priority(current_char, has_intro)
