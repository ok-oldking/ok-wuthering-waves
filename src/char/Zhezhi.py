import time
from src.char.BaseChar import BaseChar

class Zhezhi(BaseChar):
    #not tested, based on video footage might have too long field time rotation ?
    def count_liberation_priority(self):
        return 30 
    def do_perform(self):
        if self.has_intro:
            n, i = 0.2, 0
            while not self.is_forte_full() or i > 15:# 15xN = 3 sec at max
                self.normal_attack()
                self.sleep(n)
                i+=1
        self.click_liberation()
        if self.is_forte_full():
            self.click_resonance(post_sleep=0.5)
            self.normal_attack()
        self.click_echo_and_swapout()
        self.click_resonance()
        self.switch_next_char()
    
