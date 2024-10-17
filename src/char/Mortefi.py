from src.char.BaseChar import BaseChar


class Mortefi(BaseChar):
    def do_perform(self):
        self.click_liberation()
        self.click_resonance()
        self.click_echo()
        self.switch_next_char()
