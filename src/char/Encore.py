from src.char.BaseChar import BaseChar


class Encore(BaseChar):
    def do_perform(self):
        if self.has_intro and self.liberation_available():
            self.click_liberation()
            self.sleep(2)
            self.normal_attack()
            self.sleep(.4)
            self.normal_attack()
            self.sleep(.4)
            self.normal_attack()
            self.sleep(.4)
            self.normal_attack()
        elif self.resonance_available():
            self.click_resonance()
            self.sleep(0.2)
        elif self.echo_available():
            self.click_echo()
            self.sleep(0.3)
        self.switch_next_char()
