from src.char.BaseChar import BaseChar

class Baizhi(BaseChar):
    def do_perform(self):
        if self.has_intro:
            while not self.is_forte_full():
                self.normal_attack()
                self.sleep(0.2)
        if not self.is_con_full():
            self.click_liberation()
        if not self.is_con_full():
            self.click_resonance()
        self.click_echo()
        self.switch_next_char()
