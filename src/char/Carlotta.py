import time
import cv2
import numpy as np

from ok import color_range_to_bound
from src.char.BaseChar import BaseChar, Priority


class Carlotta(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.switch_lock = -1
        self.press_w = -1
        self.char_zhezhi = None
        self.forte = 0
        self.continue_liberation = False
        self.liberation_ready = False

    def reset_state(self):
        super().reset_state()
        self.switch_lock = -1
        self.press_w = -1
        self.char_zhezhi = None
        self.forte = 0
        self.continue_liberation = False
        self.liberation_ready = False
        
    def do_perform(self):
        if self.press_w == -1:
            self.decide_teammate()               
        if self.char_zhezhi is not None:
            return self.do_perform_interlock()
        self.bullet = 0
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.3 sec')
            self.bullet = 1
            self.continues_normal_attack(1.3)
        if self.is_forte_full():
            self.heavy_attack()
            return self.switch_next_char()
        if self.liberation_available() and not self.need_fast_perform():
            if self.press_w == 1:
                self.task.send_key_down(key='w')
                while self.liberation_available():                
                    self.click_liberation()
                    self.task.send_key_up(key='w')
                    self.check_combat()
                    self.task.send_key_down(key='w')
                self.task.send_key_up(key='w')
            else:
                while self.liberation_available():                
                    self.click_liberation()
                    self.check_combat()
            self.click_echo()
            self.last_echo = time.time()
            return self.switch_next_char()
        if self.resonance_available():
            if self.bullet == 0:
                self.heavy_attack()
            if self.click_resonance()[0]:
                return self.switch_next_char()
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()
        self.continues_normal_attack(0.31)
        self.switch_next_char()

    def has_long_actionbar(self):
        return True
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.press_w == -1:
            self.decide_teammate()
        if has_intro and self.check_outro() in {'char_zhezhi'}:
            return Priority.MAX
        if self.char_zhezhi is not None and self.forte == 0:
            return Priority.FAST_SWITCH+1
        else:
            return super().do_get_switch_priority(current_char, has_intro)
            
    def click_liberation(self, con_less_than=-1, send_click=False, wait_if_cd_ready=0, timeout=5):
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
        while self.liberation_available():  # clicked and still in team wait for animation
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
            # new
            if self.task.in_team()[0]:
                if self.press_w == 1:
                    self.task.send_key_up(key='w')
                    self.check_combat()
                    self.task.send_key_down(key='w')
                else:
                    self.check_combat()
            else:
                break
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
        while not self.task.in_team()[0]:
            self.task.in_liberation = True
            if not clicked:
                clicked = True
                self.update_liberation_cd()
            if send_click:
                self.click(interval=0.1)
            if time.time() - start > 7:
                self.task.in_liberation = False
                self.task.raise_not_in_combat('too long a liberation, the boss was killed by the liberation')
            self.task.next_frame()
        duration = time.time() - start
        self.add_freeze_duration(start, duration)
        self.task.in_liberation = False
        if clicked:
            self.logger.info(f'click_liberation end {duration}')
        return clicked

    def decide_teammate(self):
        from src.char.Zhezhi import Zhezhi
        self.press_w = 0
        if self.task.name and self.task.name == "Farm 4C Echo in Dungeon/World":
            self.press_w = 1
        elif char := self.task.has_char(Zhezhi):
            self.char_zhezhi = char
            self.char_zhezhi.char_carlotta = self

    def get_forte(self):
        if self.is_forte_full():
            return 4
        box = self.task.box_of_screen_scaled(5120, 2880, 2164, 2670, 2900, 2680, name='carlotta_forte', hcenter=True)
        self.forte = self.calculate_forte_num(carlotta_forte_color,box,4,9,11,100)
        return self.forte
        
    def get_ready(self):
        self.logger.debug(f'carlotta_state :{self.forte},{self.resonance_available(check_cd = True)}')
        return (self.forte > 2) or (self.resonance_available(check_cd = True) and self.forte > 0) or self.liberation_ready 
        
    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        if check_cd and self.time_elapsed_accounting_for_freeze(self.last_res) < self.res_cd:
            return False
        if self._resonance_available:
            return True
        if self.is_current_char:
            snap = self.current_resonance() if current is None else current
            if check_ready and snap == 0:
                return False
            self._resonance_available = self.is_available(snap, 'resonance')
        elif self.res_cd > 0:
            return time.time() - self.last_res > self.res_cd
        return self._resonance_available
        
    def do_perform_interlock(self):
        self.bullet = 0
        if self.has_intro:
            self.bullet = 1
            self.continues_normal_attack(1.3) 
            if self.check_outro() in {'char_zhezhi'}:
                self.do_perform_outro()
                return self.switch_next_char()
        if self.get_forte() < 4 and self.resonance_available() and not self.liberation_ready:
            if self.bullet == 0:
                self.heavy_attack()
            if self.click_resonance()[0]:               
                self.forte += 2
                self.switch_lock = time.time()
                return self.switch_next_char()  
        if self.get_ready():
            self.continue_liberation = False
        if self.is_forte_full():
            self.heavy_attack()
            self.liberation_ready = True
            return self.switch_next_char()            
        if self.liberation_available() and self.continue_liberation:
            while self.liberation_available():                
                if self.click_liberation():
                    self.continue_liberation = False
                    self.liberation_ready = False
                self.check_combat()
        if self.echo_available():
            self.click_echo()
        self.continues_normal_attack(0.31)
        self.switch_next_char()          

    def do_perform_outro(self):
        res = True
        self.char_zhezhi.forte = 0
        self.get_forte()
        if not self.liberation_ready and self.time_elapsed_accounting_for_freeze(self.last_perform) < 5:
            while not self.is_forte_full():
                if self.click_resonance()[0]:
                    self.continues_normal_attack(1)
                else:
                    self.click_with_interval()
                self.check_combat()
        self.task.mouse_down()
        start = time.time()
        while time.time() - start < 1.5:
            if not self.is_forte_full():
                break
            self.liberation_ready = True
            self.forte = 0
            self.task.next_frame()
        self.task.mouse_up()
        self.check_combat()        
        self._liberation_available == False
        self._resonance_available == False
        click = False
        liber = False
        if self.liberation_ready:
            while self.time_elapsed_accounting_for_freeze(self.last_perform) < 14:
                if self.liberation_available() and not liber:
                    while self.liberation_available():             
                        if self.click_liberation():
                            self.liberation_ready = False
                            liber = True
                            self.forte = 0
                        self.check_combat()
                    if liber:
                        self.sleep(0.2)
                if self.click_resonance()[0]:
                    self.continues_normal_attack(0.8)
                    self.forte += 1
                    click = True
                self.click_with_interval(0.1)
                if not self.liberation_available() and not self.resonance_available() and click:
                    break
                self.check_combat()               
        if self.click_echo(time_out=2):
            self.switch_lock = time.time()
        self.continue_liberation = not liber
        
    def wait_switch(self):
        if self.has_intro and self.time_elapsed_accounting_for_freeze(self.switch_lock, True) < 2.5:
            return True
        return False
        
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
        
carlotta_forte_color = {
    'r': (70, 100),  # Red range
    'g': (195, 225),  # Green range
    'b': (235, 255)   # Blue range
} #85,209,251
