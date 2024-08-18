from src.char.BaseChar import BaseChar


class Mortefi(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.wait_down()
        else:
            self.click_liberation()
            self.click_resonance()
            self.click_echo(sleep_time=0.1)
        self.switch_next_char()
