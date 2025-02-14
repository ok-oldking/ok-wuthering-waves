import time

from src.char.BaseChar import BaseChar, Priority

class Phoebe(BaseChar):
    def __init__(self, *args):
        super().__init__(*args)
        self.first_liberation = False
        self.perform_intro = 0
        
    def reset_state(self):
        super().reset_state()
        self.first_liberation = False
        self.perform_intro = 0
    
    def flying(self):
        return self.current_resonance() == 0 or self.current_echo() == 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.5)
            if not self.in_absolutin():
                self.starflash_combo() 
                return self.switch_next_char()
        if self.flying():
            self.logger.debug('Pheobe flying')
            self.continues_normal_attack(0.1)
            return self.switch_next_char()
        if self.liberation_available() and self.first_liberation:
            self.click_liberation()
            self.starflash_combo() 
            return self.switch_next_char()
        if self.resonance_available():
            self.click_resonance_once()
            self.starflash_combo()                                   
            return self.switch_next_char()        
        if self.click_echo():
            return self.switch_next_char()
        self.continues_normal_attack(0.1)
        self.switch_next_char()

    def starflash_combo(self):
        start = time.time()
        if not self.heavy_attack_ready():
            while not self.heavy_attack_ready():
                self.check_combat()
                if time.time() - start > 5:
                    break
                if time.time() - start > 0.5 and not self.in_absolutin():
                    return
                self.click()
                self.task.next_frame()
            self.heavy_attack()
        else:
            self.heavy_attack(1.2)
        self.first_liberation = True
        if self.is_con_full():
            self.sleep(0.3)
                
    def click_resonance_once(self):
        start = time.time()
        while self.resonance_available():
            self.check_combat()
            if time.time() - start > 0.1:
                break
            self.task.send_key(self.get_resonance_key())
            self.task.next_frame()
    
    def litany_ready(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3149, 1832, 3225, 1857, name='phoebe_resonance', hcenter=True)
        blue_percent = self.task.calculate_color_percentage(phoebe_blue_color, box)
        self.logger.info(f'blue_percent {blue_percent}')
        return blue_percent > 0.15        

    def heavy_attack_ready(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 2740, 1832, 2803, 1857, name='phoebe_attack', hcenter=True)
        light_percent = self.task.calculate_color_percentage(phoebe_light_color, box)
        self.logger.info(f'light_percent {light_percent}')
        if not self.in_absolutin():
            self.logger.info(f'litany_light_percent {light_percent}')
        if light_percent > 0.15 or self.is_forte_full() or self.litany_ready():
            return True
        blue_percent = self.task.calculate_color_percentage(phoebe_blue_color, box)
        return blue_percent > 0.15
        
    def in_absolutin(self):           
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 1987, 1671, 2008, name='phoebe_forte', hcenter=True)
        forte_percent = self.task.calculate_color_percentage(phoebe_forte_light_color, box)
        if forte_percent > 0.01:
            return True
        forte_percent = self.task.calculate_color_percentage(phoebe_forte_blue_color, box) 
        return forte_percent > 0.01
            
    def has_long_actionbar(self):
        return True
        
    def switch_next_char(self, *args):
        if self.is_con_full():
            self.perform_intro = time.time()
        return super().switch_next_char(*args)
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.perform_intro) < 4.0:
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)
    
            
phoebe_blue_color = {
    'r': (140, 170),  # Red range
    'g': (205, 235),  # Green range
    'b': (240, 255)   # Blue range
}  

phoebe_light_color = {
    'r': (240, 255),  # Red range
    'g': (240, 255),  # Green range
    'b': (200, 230)   # Blue range
}  

phoebe_forte_light_color = {
    'r': (240, 255),  # Red range
    'g': (240, 255),  # Green range
    'b': (165, 195)   # Blue range
}  

phoebe_forte_blue_color = {
    'r': (220, 250),  # Red range
    'g': (225, 255),  # Green range
    'b': (185, 215)   # Blue range
}  