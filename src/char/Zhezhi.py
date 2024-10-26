from src.char.BaseChar import BaseChar

class Zhezhi(BaseChar):
    #not tested, based on video footage
    def count_liberation_priority(self):
        return 30 
    def do_perform(self):
        if self.has_intro:
            while not self.is_forte_full(): 
                self.normal_attack()
                self.sleep(0.2)
        self.click_liberation()
        if self.is_forte_full():
            self.click_resonance(post_sleep=0.5)
            self.normal_attack()
        if self.click_echo():
            return self.switch_next_char()
        self.click_resonance()
        self.switch_next_char()
    
