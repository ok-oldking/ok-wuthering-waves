import time

from src.char.BaseChar import BaseChar


class Qiuyuan(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.17)
        if self.flying():
            self.wait_down()            
        start = time.time()
        timeout = lambda: time.time() - start < 1.2
        if self.has_intro:
            timeout = lambda: time.time() - start < 4
        while timeout():        
            self.click_echo(time_out=0)
            if time.time() - start < 0.5 and self.click_liberation():              
                start = time.time()
            if self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
                return self.switch_next_char()
            if self.flying() and not self.is_mouse_forte_full():
                self.shorekeeper_auto_dodge()  
            self.click()
            self.check_combat()
            self.task.next_frame()
        self.click_resonance()
        self.switch_next_char()
        
    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)
