import time
import cv2
import numpy as np

from src.char.Healer import Healer, Priority
from ok import color_range_to_bound


class Verina(Healer):
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
            if n[i] > amplitude:
                amplitude = n[i]
                frequncy = i
            i += 1
        self.logger.debug(f'forte with freq {frequncy} & amp {amplitude}')
        return (min_freq <= frequncy <= max_freq) or amplitude >= min_amp

    def calculate_forte_num(self, forte_color, box, num=1, min_freq=39, max_freq=41, min_amp=50):
        cropped = box.crop_frame(self.task.frame)
        lower_bound, upper_bound = color_range_to_bound(forte_color)
        image = cv2.inRange(cropped, lower_bound, upper_bound)

        forte = 0
        height, width = image.shape
        step = int(width / num)

        forte = num
        left = step * (forte - 1)
        while forte > 0:
            gray = image[:, left:left + step]
            score = self.judge_frequncy_and_amplitude(gray, min_freq, max_freq, min_amp)
            if score:
                break
            left -= step
            forte -= 1
        self.logger.info(f'Frequncy analysis with forte {forte}')
        return forte

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if isinstance(current_char, Healer):
            return Priority.MIN
        if self.last_res > 0 and self.time_elapsed_accounting_for_freeze(self.last_res) < self.res_cd:
            return Priority.MIN
            
        time_elapsed = self.time_elapsed_accounting_for_freeze(self.last_perform)
        
        if time_elapsed >= 18:
            return Priority.SKILL_AVAILABLE * 2
        if has_intro and time_elapsed >= 12:
            return Priority.SKILL_AVAILABLE
            
        return Priority.MIN

    def _force_cast_resonance(self):
        clicked_res = False
        res_clicked_time = 0
        res_start = time.time()
        while time.time() - res_start < 2.5:
            if self.resonance_available():
                clicked_res = self.click_resonance(send_click=False)[0]
                if clicked_res:
                    res_clicked_time = time.time()
                    break
            
            self.send_resonance_key()
            
            if self.task.has_cd('resonance'):
                clicked_res = True
                res_clicked_time = time.time()
                self.update_res_cd()
                break
            
            if self.is_con_full():
                break
                
            self.task.next_frame()
            
        if clicked_res:
            self.sleep(0.1)
            
        self.logger.info(f"Verina: has_intro={self.has_intro}, clicked_res={clicked_res}")
        return res_clicked_time

    def _consume_forte_energy(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2016, name='verina_forte', hcenter=True)
        self.current_forte_energy = self.calculate_forte_num(verina_yellow_color, box, 4, 39, 41, 50)
        allow_remain = 1 if self.task.char_config.get("Verina C2") else 2
        need_to_consume = self.current_forte_energy > allow_remain
        
        self.logger.info(f"Verina: pre-consume current_forte_energy={self.current_forte_energy}, is_con_full={self.is_con_full()}, need_to_consume={need_to_consume}")
        
        if self.current_forte_energy >= 1 and (not self.is_con_full() or need_to_consume):
            if self.current_forte_energy == 1:
                self.logger.info("Verina: consume 1 (heavy_attack)")
                self.heavy_attack(0.6)
            
            elif self.current_forte_energy in [2, 3]:
                self.logger.info(f"Verina: consume {self.current_forte_energy} (jump + aerial fast click)")
                self.task.jump(after_sleep=0.05)
                self.continues_normal_attack(duration=0.8, interval=0.1, until_con_full=not need_to_consume)
                
            elif self.current_forte_energy >= 4:
                self.logger.info("Verina: consume 4 (smart heavy slide + aerial fast click)")
                self.task.mouse_down()
                start_slide = time.time()
                while time.time() - start_slide < 1.0:
                    if time.time() - start_slide > 0.3 and self.flying():
                        self.logger.info("Verina: Hit enemy and flying detected, releasing slide!")
                        break
                    self.task.next_frame()
                self.task.mouse_up()
                
                self.sleep(0.2)
                self.continues_normal_attack(duration=0.8, interval=0.1, until_con_full=not need_to_consume)
                
            self.current_forte_energy = 0

    def do_perform(self):
        if self.has_intro:
            self.sleep(0.8)
        else:
            self.sleep(0.1)
            
        res_clicked_time = self._force_cast_resonance()
        
        self.click_echo()
        if self.click_liberation():
            self.sleep(0.3)
            
        if res_clicked_time > 0:
            elapsed_since_res = time.time() - res_clicked_time
            if elapsed_since_res < 0.5:
                self.sleep(0.5 - elapsed_since_res)
                
        self._consume_forte_energy()
        
        self.switch_next_char()

verina_yellow_color = {
    'r': (240, 255),
    'g': (220, 255),
    'b': (100, 160)
}
