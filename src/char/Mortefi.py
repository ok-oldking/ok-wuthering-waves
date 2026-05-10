from src.char.BaseChar import BaseChar


class Mortefi(BaseChar):
    def do_perform(self):
        self.wait_down()
        liberated = self.click_liberation()
        self.click_resonance()
        self.click_echo()
        if not liberated:
            self.click_liberation(wait_if_cd_ready=1)
        self.switch_next_char()
