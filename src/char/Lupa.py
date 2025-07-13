import time
import cv2
import numpy as np

from ok import color_range_to_bound
from src.char.BaseChar import BaseChar, Priority


class Lupa(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wolf = False
        
    def reset_state(self):
        super().reset_state()
        self.wolf = False
        
    def do_perform(self):
        in_outro = False       
        if self.has_intro:
            self.continues_normal_attack(1)
            if self.check_outro() in {'chang_changli', 'char_changli2'}:
                in_outro = True            
        self.click_echo(time_out=0)
        if self.res_wolf() and not in_outro:
            return self.switch_next_char()
        if self.judge_forte() == 2 and not self.task.find_one('lupa_wolf_icon2', threshold=0.85):
            self.logger.debug('perform forte full')
            if self.flying():
                self.task.wait_until(lambda: not self.is_forte_full(), post_action=self.click_with_interval, time_out=2)
            else:
                self.heavy_attack()
                self.task.wait_until(lambda: not self.is_forte_full(), post_action=self.click_with_interval, time_out=1.4)
            if not self.is_forte_full():
                self.wolf = True
            if in_outro:
                self.task.wait_until(lambda: self.task.find_one('lupa_wolf_icon2', threshold=0.85), post_action=None, time_out=0.5)
                self.res_wolf()
            else:
                return self.switch_next_char()
        if self.current_resonance() > 0.1 and self.click_resonance()[0]:
            self.last_liberation = -1
            if self.liberation_available():
                self.sleep(0.3)
            else:
                return self.switch_next_char()
        if (in_outro or not self.need_fast_perform()) and self.click_liberation():
            self.continues_normal_attack(0.3)
            if in_outro:
                self.continues_normal_attack(1)
            else:
                return self.switch_next_char() 
        if self.still_in_liberation():
            self.logger.debug('perform in liberation')
            self.click_jump_with_click(4)
            if self.flying():
                self.task.wait_until(lambda: not self.is_forte_full(), post_action=self.click_with_interval, time_out=2)
            else:
                self.heavy_attack()
                self.task.wait_until(lambda: not self.is_forte_full(), post_action=self.click_with_interval, time_out=1.4)
            if not self.is_forte_full():
                self.wolf = True
            if in_outro:
                self.task.wait_until(lambda: self.task.find_one('lupa_wolf_icon2', threshold=0.85), post_action=None, time_out=0.5)
                self.res_wolf()
            return self.switch_next_char()       
        self.continues_normal_attack(0.1)
        self.switch_next_char()
        
    def still_in_liberation(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation) < 12     

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.still_in_liberation():
            return Priority.MAX
        if has_intro and current_char.char_name in {'chang_changli'}:
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)
        
    def click_jump_with_click(self, delay=0.1):
        start = time.time()
        click = 0
        while True:
            if time.time() - start > delay:
                break
            if click == 0:
                self.task.send_key('SPACE')
            else:
                self.click()
            click = 1 - click
            if self.judge_forte() == 2:
                return
            self.check_combat()
            self.task.next_frame()
           
    def res_wolf(self, timeout = 1):
        self.logger.debug('perform res wolf')
        start = time.time() 
        click = False
        while True:
            if self.wolf and time.time() - start < 0.2:
                pass
            elif not self.task.find_one('lupa_wolf_icon2', threshold=0.85):
                break
            self.send_resonance_key()
            click = True
            if time.time() - start > timeout:
                break
            self.check_combat()
            self.task.next_frame()
        if click:
            self.last_liberation = -1
            self.wolf = False
            self.task.wait_until(lambda: self.get_current_con() >= 1, post_action=self.click_with_interval, time_out=1)
            self.sleep(0.2)
        return click
        
   
    def judge_forte(self):
        if not self.is_forte_full():
            return 0
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2016, name='lupa_forte', hcenter=True)
        forte = self.calculate_forte_num(lupa_red_color,box,2,19,21,400)
        return forte
        
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
        self.logger.info(f'forte with freq {frequncy} & amp {amplitude}')
        return (min_freq <= frequncy <= max_freq) or amplitude >= min_amp
        
    def calculate_forte_num(self, forte_color, box, num = 1, min_freq = 39, max_freq = 41, min_amp = 50):
        cropped = box.crop_frame(self.task.frame)
        lower_bound, upper_bound = color_range_to_bound(forte_color)
        image = cv2.inRange(cropped, lower_bound, upper_bound)
        
        forte = 0
        height, width = image.shape
        step = int(width / num)
        
        forte = num
        left = step * (forte-1)
        while forte > 0:
            gray = image[:,left:left+step]
            score = self.judge_frequncy_and_amplitude(gray,min_freq,max_freq,min_amp)
            if score:
                break
            left -= step
            forte -= 1
        self.logger.info(f'Frequncy analysis with forte {forte}')    
        return forte
        
lupa_red_color = {
    'r': (235, 255),  # Red range
    'g': (75, 105),  # Green range
    'b': (75, 105)  # Blue range
}  #250,99,107
