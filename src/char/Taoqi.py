from src.char.BaseChar import BaseChar


class Taoqi(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.sleep(0.8)
            self.normal_attack()
            self.sleep(.4)
            self.normal_attack()
            self.sleep(.4)
            self.normal_attack()
            self.sleep(.4)
        self.click_liberation()
        self.click_resonance()
        self.click_echo(sleep_time=0.1)
        self.switch_next_char()
