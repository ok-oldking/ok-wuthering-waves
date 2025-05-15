import time
import cv2
import numpy as np
from src.char.BaseChar import BaseChar, Priority
from ok import color_range_to_bound

class Phoebe(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_liberation = False
        self.perform_intro = 0
        self.attribute = 0
        self.star_available = False
        self._heavy_attack = True
        self.last_holding = 0
        
    def reset_state(self):
        super().reset_state()
        self.first_liberation = False
        self.perform_intro = 0
        self.attribute = 0
        self.star_available = False
        self._heavy_attack = True
        
    def flying(self):
        return self.current_resonance() == 0 or self.current_echo() == 0

    def do_perform(self):
        if self.attribute == 0:
            self.decide_teammate()
        if self.has_intro:
            self.continues_normal_attack(0.8)
            if self.heavy_attack_ready():
                self.perform_heavy_attack(0.8)
                return self.switch_next_char()
        if self.attribute == 1:
            self.click_echo()
        if self.flying():
            self.logger.info('Pheobe flying')
            self.continues_normal_attack(0.1)
            return self.switch_next_char()
        if self.liberation_available() and self.first_liberation:
            self.click_liberation()
            self.sleep(0.2)
        if self.heavy_attack_ready():
            self.starflash_combo()
            return self.switch_next_char()
        if self.resonance_available() and self.click_resonance()[0]:
            return self.switch_next_char()
        if self.judge_forte() > 0:
            self.starflash_combo()  
        if self.attribute==2 and self.click_echo():
            return self.switch_next_char()
        self.continues_normal_attack(0.1)
        self.switch_next_char()

    def judge_forte(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2014, name='phoebe_forte1', hcenter=True)
        forte = self.calculate_forte_num(phoebe_forte_blue_color,box,2,18,20,50)
        if forte > 0:
            return forte
        forte = self.calculate_forte_num(phoebe_forte_light_color,box,4,9,11,25)
        return forte
            
    def starflash_combo(self):
        start = time.time()
        check_forte = start
        if not self.heavy_attack_ready():
            while not self.heavy_attack_ready():
                self.click()
                if time.time() - start > 5:
                    break
                if time.time() - check_forte > 1 and self.judge_forte() == 0:                
                    return False
                else:
                    check_forte = time.time()
                self.check_combat()
                self.task.next_frame()
            self.perform_heavy_attack()
        else:
            self.perform_heavy_attack(1)
        self.first_liberation = True
        if self.is_con_full():
            self.sleep(0.3)
        return True
                
    def perform_heavy_attack(self, duration=0.6):    
        if self.attribute == 2 and (self.litany_ready() or self.judge_forte() == 0 or not self.check_middle_star()):
            self.hold_resonance(duration=duration)
            self.last_holding = time.time()
        else:
            self.heavy_attack(duration=duration)
        self._heavy_attack = False

    def click_resonance_once(self):
        start = time.time()
        while self.resonance_available():
            self.check_combat()
            if time.time() - start > 0.5:
                return True
            self.send_resonance_key()
            self.task.next_frame()
        return False
            
    def hold_resonance(self, duration=0.6):        
        self.check_combat()
        self.logger.debug('hold resonance start')
        self.task.send_key_down(self.get_resonance_key())
        self.sleep(duration)
        self.task.send_key_up(self.get_resonance_key())
        self.logger.debug('hold resonance end')
    
    def litany_ready(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3149, 1832, 3225, 1857, name='phoebe_resonance', hcenter=False)
        blue_percent = self.task.calculate_color_percentage(pheobe_litany_blue_color, box)
        self.logger.debug(f'blue_percent {blue_percent}')
        return blue_percent > 0.15        

    def heavy_attack_ready(self):
        if self._heavy_attack:
            return True
        box = self.task.box_of_screen_scaled(3840, 2160, 2740, 1832, 2803, 1857, name='phoebe_attack', hcenter=False)
        light_percent = self.task.calculate_color_percentage(phoebe_light_color, box)
        self.logger.debug(f'light_percent {light_percent}')
        if light_percent > 0.15 and (self.is_forte_full() or self.litany_ready()):
            self._heavy_attack = True
            return True
        blue_percent = self.task.calculate_color_percentage(phoebe_blue_color, box)
        self._heavy_attack = blue_percent > 0.15 and self.is_forte_full()
        return self._heavy_attack
                    
    def has_long_actionbar(self):
        return True
        
    def switch_next_char(self, *args):
        if self.is_con_full():
            self.perform_intro = time.time()
        self.heavy_attack_ready()
        
        return super().switch_next_char(*args)
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.perform_intro) < 4.5:
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)
            
    def check_middle_star(self):
        if self.star_available:
            return True
        box = self.task.box_of_screen_scaled(3840, 2160, 1890, 2010, 1930, 2030, name='phoebe_middle_star', hcenter=True)
        forte_percent = self.task.calculate_color_percentage(phiebe_star_light_cloor, box)
        self.logger.info(f'middle_star_light_percent {forte_percent}')
        if forte_percent > 0.1:
            self.star_available = True
            return True
        forte_percent = self.task.calculate_color_percentage(phiebe_star_blue_cloor, box)
        self.logger.info(f'middle_star_blue_percent {forte_percent}')
        if forte_percent > 0.1:
            self.star_available = True
            return True    
        return False
        
    def decide_teammate(self):
        for i, char in enumerate(self.task.chars):
            self.logger.debug(f'phoebe teammate char: {char.char_name}')
            if char.char_name == 'char_zani':
                self.logger.debug(f'phoebe set attribute: support')
                self.attribute = 2
                return
        self.logger.debug(f'phoebe set attribute: attacker')
        self.attribute = 1
        return 
    
    def judge_frequncy_and_amplitude(self, gray, min_freq, max_freq, min_amp):
        height, width = gray.shape[:]
        if height == 0 or width < 64 or not np.array_equal(np.unique(gray), [0, 255]):
            return 0       

        white_ratio = np.count_nonzero(gray == 255) / gray.size
        profile = np.sum(gray == 255, axis=0).astype(np.float32)
        profile -= np.mean(profile)
        n = np.abs(np.fft.fft(profile))
        amplitude = 0
        frequncy = 0
        i = 1
        while i < width:
            if n[i]> amplitude:
                amplitude = n[i]
                frequncy = i
            i+=1
        return (min_freq <= i <= max_freq) or amplitude >= min_amp
        
    def calculate_forte_num(self, forte_color, box, num = 1, min_freq = 39, max_freq = 41, min_amp = 50):
        cropped = box.crop_frame(self.task.frame)
        lower_bound, upper_bound = color_range_to_bound(forte_color)
        image = cv2.inRange(cropped, lower_bound, upper_bound)
        
        forte = 0
        height, width = image.shape
        step = int(width / num)
        left = 0
        fail_count = 0
        warning = False
        while left+step < width:
            gray = image[:,left:left+step] 
            score = self.judge_frequncy_and_amplitude(gray,min_freq,max_freq,min_amp)
            if fail_count == 0:
                if score:
                    forte += 1
                else:
                    fail_count+=1
            else:
                if score:
                    warning = True
                else:
                    fail_count+=1
            left+=step
        if warning:
            self.logger.info('Frequncy analysis error, return the forte before mistake.')
        self.logger.info(f'Frequncy analysis with forte {forte}')    
        return forte
  
phoebe_blue_color = {
    'r': (130, 170),  # Red range
    'g': (205, 235),  # Green range
    'b': (240, 255)   # Blue range
}  

pheobe_litany_blue_color = {
    'r': (115, 170),  # Red range
    'g': (160, 235),  # Green range
    'b': (230, 255)   # Blue range
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
    'r': (225, 255),  # Red range
    'g': (225, 255),  # Green range
    'b': (190, 225)   # Blue range
}  

phiebe_star_light_cloor = {
    'r': (235, 255),  # Red range
    'g': (220, 250),  # Green range
    'b': (160, 190)   # Blue range
}  

phiebe_star_blue_cloor = {
    'r': (240, 255),  # Red range
    'g': (240, 255),  # Green range
    'b': (240, 255)   # Blue range
}  