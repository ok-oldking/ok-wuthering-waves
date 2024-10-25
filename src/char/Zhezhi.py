from src.char.BaseChar import BaseChar

class Zhezhi(BaseChar):
    #not tested, based on video footage
    def count_liberation_priority(self):
        return 30
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.5)
        if self.liberation_available():
            self.click_liberation()
        if self.is_con_full():
            self.click_resonance(post_sleep=0.4)
            self.normal_attack()
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()
        if self.resonance_available():
            self.click_resonance
            return self.switch_next_char()
        
