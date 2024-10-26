from src.char.BaseChar import BaseChar, WWRole

class Danjin(BaseChar):
    def count_resonance_priority(self):
        return 0
    def do_perform(self):
        if self.is_forte_full():
                self.heavy_attack()
                self.sleep(0.25)
                self.normal_attack()
        self.click_liberation()
        if self.click_echo():
            return self.switch_next_char()

        self.continues_normal_attack(0.8)
        self.click_resonance(post_sleep=0.4)
        self.click_resonance(post_sleep=0.2)
        self.switch_next_char()
        