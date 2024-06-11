from src.char.BaseChar import BaseChar


class Taoqi(BaseChar):
    def perform(self):
        if self.has_intro:
            self.normal_attack()
            self.sleep(0.3)
            self.normal_attack()
            self.sleep(0.3)
            self.normal_attack()
            self.sleep(0.3)
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
