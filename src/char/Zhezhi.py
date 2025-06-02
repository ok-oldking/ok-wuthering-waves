import time
from src.char.BaseChar import BaseChar

class Zhezhi(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resonance_blue = False

    def reset_state(self):
        super().reset_state()
        self._resonance_blue = False
        
    def do_perform(self):
        if self.has_intro:
            self.add_freeze_duration(time.time(), 0.5)
            self.continues_normal_attack(1.5)
        self.click_liberation()               
        if (self._resonance_blue or self.resonance_blue()) and self.resonance_available():
            self._resonance_blue = False
            self.resonance_until_not_blue()  
            return self.switch_next_char()
        elif self.resonance_available() and not self.is_forte_full():
            pass
        elif self.resonance_available() and self.is_forte_full():
            self.click_resonance()
            self.continues_normal_attack(0.8)
            self._resonance_blue = True
            return self.switch_next_char()
        if not self.click_echo():
            self.continues_normal_attack(0.1)
        self.switch_next_char()
            
    def resonance_blue(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3105, 1845, 3285, 2010, name='zhezhi_resonance', hcenter=True)
        blue_percent = self.task.calculate_color_percentage(zhezhi_blue_color, box)
        return blue_percent > 0.005           
        
    def resonance_until_not_blue(self):
        start = time.time()
        while not self.resonance_blue():
            if time.time() - start > 1:
                break
            self.check_combat()
            self.task.next_frame()
        while self.resonance_available() and self.resonance_blue():
            self.send_resonance_key()   
            if self.need_fast_perform() and time.time() - start > 1.1:
                break
            if self.is_con_full():
                break
            if time.time() - start > 4:
                break
            self.check_combat()
            self.task.next_frame()
        
zhezhi_blue_color = {
    'r': (160, 180),  # Red range
    'g': (240, 255),  # Green range
    'b': (245, 255)  # Blue range
}  