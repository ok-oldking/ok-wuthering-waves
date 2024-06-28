from src.char.BaseChar import BaseChar


class Taoqi(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.wait_down()
            self.continues_normal_attack(2.5)
        else:
            self.click_liberation()
            self.click_resonance()
            self.click_echo(sleep_time=0.1)
        self.switch_next_char()
