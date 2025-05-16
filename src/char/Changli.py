import time
import cv2
import numpy as np
from ok import color_range_to_bound
from src.char.BaseChar import BaseChar, Priority

class Changli(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enhanced_normal = False

    def reset_state(self):
        super().reset_state()
        self.enhanced_normal = False
        
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.4)
            self.enhanced_normal = True
        forte = self.judge_forte()
        if self.enhanced_normal:
            self.logger.debug('Changli has enhanced')
            self.continues_normal_attack(0.4)
            forte += 1
        self.enhanced_normal = False
        if forte >= 4 or self.is_forte_full():
            self.heavy_attack()
        #如果处于空中需要重击两次
            if self.is_forte_full():
                self.heavy_attack()
            self.check_combat()
            return self.switch_next_char()
        if not(forte >= 3 and self.resonance_available()) and self.liberation_available():   
            if self.liberation_and_heavy():               
                return self.switch_next_char()
        if self.current_resonance() > 0 and self.resonance_available():
            self.send_resonance_key()
            self.enhanced_normal = True
            return self.switch_next_char()        
        if self.click_echo():
            return self.switch_next_char()
        self.continues_normal_attack(0.1)
        self.switch_next_char()

    def judge_forte(self):
        if self.is_forte_full():
            return 4
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2016, name='changli_forte', hcenter=True)
        forte = self.calculate_forte_num(changli_red_color,box,4,9,11,25)
        return forte
        
    def liberation_and_heavy(self, con_less_than=-1, send_click=False, wait_if_cd_ready=0, timeout=5):
        if con_less_than > 0:
            if self.get_current_con() > con_less_than:
                return False
        self.logger.debug('click_liberation start')
        start = time.time()
        last_click = 0
        clicked = False
        while time.time() - start < wait_if_cd_ready and not self.liberation_available() and not self.has_cd(
                'liberation'):
            self.logger.debug(f'click_liberation wait ready {wait_if_cd_ready}')
            if send_click:
                self.click(interval=0.1)
            self.task.next_frame()
        while self.liberation_available() and self.task.in_team()[0]:  # clicked and still in team wait for animation
            self.logger.debug('click_liberation liberation_available click')
            now = time.time()
            if now - last_click > 0.1:
                self.send_liberation_key()
                if not clicked:
                    clicked = True
                    self.update_liberation_cd()
                last_click = now
            if time.time() - start > timeout:
                self.task.raise_not_in_combat('too long clicking a liberation')
            self.task.next_frame()
        if clicked:
            if self.task.wait_until(lambda: not self.task.in_team()[0], time_out=0.4):
                self.task.in_liberation = True
                self.logger.debug('not in_team successfully casted liberation')
            else:
                self.task.in_liberation = False
                self.logger.error('clicked liberation but no effect')
                return False
        start = time.time()
        hold = False
        while not self.task.in_team()[0]:
            self.task.in_liberation = True
            if not clicked:
                clicked = True
                self.update_liberation_cd()
            if send_click:
                self.click(interval=0.1)
            if time.time() - start > 1.5 and not hold:
                self.task.mouse_down()
                hold = True
            if time.time() - start > 7:
                self.task.in_liberation = False
                self.task.raise_not_in_combat('too long a liberation, the boss was killed by the liberation')
            self.task.next_frame()
        duration = time.time() - start
        self.add_freeze_duration(start, duration)
        self.task.in_liberation = False
        if clicked:
            self.logger.info(f'click_liberation end {duration}')
            self.sleep(0.6)
        self.task.mouse_up()
        self.check_combat()
        return clicked   

    def judge_frequncy_and_amplitude(self, gray, min_freq, max_freq, min_amp):
        height, width = gray.shape[:]
        if height == 0 or width < 64 or not np.array_equal(np.unique(gray), [0, 255]):
            return 0       

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
        self.logger.debug(f'forte with freq {frequncy} & amp {amplitude}')
        return (min_freq <= frequncy <= max_freq) or amplitude >= min_amp
        
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
        
changli_red_color = {
    'r': (240, 255),  # Red range
    'g': (85, 105),  # Green range
    'b': (95, 115)  # Blue range
}  