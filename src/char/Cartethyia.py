import time

from src.char.BaseChar import BaseChar, Priority


class Cartethyia(BaseChar):
    def __init__(self, *args, **kwargs):
        self.is_cartethyia = True
        super().__init__(*args, **kwargs)

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.4)   
        if self.is_small():
            self.logger.info('perform small')
            if self.liberation_available():
                self.click_echo()
                if self.click_resonance()[0]:
                    self.continues_normal_attack(1.5)
                if self.click_liberation():
                    self.is_cartethyia = False
            if not self.is_cartethyia:
                pass
            elif not self.check_sword(2):
                self.logger.info('attack2')
                self.click_echo()
                start = time.time()               
                while time.time() - start < 1.6:
                    self.click(interval=0.1)
                    if self.check_sword(2):
                        break
                    self.check_combat()
                    self.task.next_frame()
                return self.switch_next_char()
            elif not self.check_sword(1):
                self.heavy_attack()
                return self.switch_next_char()
        if not self.is_cartethyia:  
            if self.task.find_one('lib_cartethyia_big') and self.click_liberation():
                self.is_cartethyia = True
                return self.switch_next_char()
            if self.click_resonance(send_click = False)[0]:
                return self.switch_next_char()
            self.continues_normal_attack(1.9)
            if self.task.find_one('lib_cartethyia_big') and self.click_liberation():
                self.is_cartethyia = True
        self.switch_next_char()       

    def is_small(self):
        self.is_cartethyia = False
        if self.task.find_one('forte_cartethyia_space'):
            self.is_cartethyia = True
        return self.is_cartethyia
    
    def count_base_priority(self):
        return 10
        
    def check_sword(self, num):
        if (num == 2):
            box = self.task.box_of_screen_scaled(5118, 2878, 2502, 2664, 2558, 2684, name='cartethyia_sword2', hcenter=True)
            percent = self.task.calculate_color_percentage(cartethyia_sword2_color, box)
        else:
            box = self.task.box_of_screen_scaled(5118, 2878, 2252, 2632, 2306, 2680, name='cartethyia_sword1', hcenter=True)
            percent = self.task.calculate_color_percentage(cartethyia_sword1_color, box)
        self.logger.debug(f'have sword{num} percent{percent}')
        return percent > 0.1
            
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if not self.is_cartethyia:
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)

cartethyia_sword1_color = {
    'r': (60, 90),  # Red range
    'g': (115, 145),  # Green range
    'b': (200, 225)  # Blue range
}  

cartethyia_sword2_color = {
    'r': (35, 65),  # Red range
    'g': (100, 150),  # Green range
    'b': (85, 115)  # Blue range
}  