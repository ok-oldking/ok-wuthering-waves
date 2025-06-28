import time, cv2
import numpy as np
from src.char.BaseChar import BaseChar, Priority

class Cartethyia(BaseChar):
    def __init__(self, *args, **kwargs):
        self.is_cartethyia = True
        self.buffs = {'sword1': None, 'sword2': None, 'sword3': None}
        self.template_shape = None
        self.try_mid_air_attack_once = False
        super().__init__(*args, **kwargs)
        self.init_template()

    def init_template(self):
        self.template_shape = self.task.frame.shape[:2]
        template = self.task.get_feature_by_name('forte_cartethyia_sword3')
        original_mat = template.mat
        h = original_mat.shape[0]
        self.sword3_half_mat = original_mat[:int(h * 0.5)]
        target_box = self.task.get_box_by_name('forte_cartethyia_sword3')
        target_box.height = (target_box.height + 1) // 2
        self.sword3_half_box = target_box

    def on_combat_end(self, chars):
        if not self.is_cartethyia:
            next_char = str((self.index + 1) % len(chars) + 1)
            self.logger.debug(f'on_combat_end {self.index} switch next char: {next_char}')
            start = time.time()
            while time.time() - start < 6:
                self.task.load_chars()
                current_char = self.task.get_current_char(raise_exception=False)
                if not isinstance(current_char, type(self)):
                    break
                else:
                    self.task.send_key(next_char)
                self.sleep(0.2, False)
            self.logger.debug(f'on_combat_end {self.index} switch end')

    def count_base_priority(self):
        return 10
    
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.4)   
        else:
            self.click_echo(time_out=0.2)
        if self.is_small():
            self.logger.info(f'is cartethyia')
            self.wait_down()
            if self.acquire_missing_buffs():
                return self.switch_next_char()
            self.try_mid_air_attack()
            self.check_combat()
            if self.click_liberation():
                self.is_cartethyia = False
                self.last_res = -1
            else:
                self.is_small()
        else:
            self.logger.info(f'is fleurdelys')
        if self.click_resonance_with_lib_big():
            pass
        else:
            start = time.time()
            time_out = 1.1 if self.is_small() else 2.2
            while time.time() - start < time_out:
                if self.try_lib_big():
                    return self.switch_next_char()
                self.click(interval=0.15)
                self.sleep(0.05)
        self.try_lib_big()
        self.switch_next_char()

    def click_resonance_with_lib_big(self):
        if self.time_elapsed_accounting_for_freeze(self.last_res) < self.res_cd:
            return False
        send_click=True
        clicked = False
        self.logger.debug(f'click_resonance start')
        last_click = 0
        last_op = 'click'
        resonance_click_time = 0
        while True:
            if resonance_click_time != 0 and time.time() - resonance_click_time > 8:
                self.task.in_liberation = False
                self.logger.error(f'click_resonance too long, breaking {time.time() - resonance_click_time}')
                self.task.screenshot('click_resonance too long, breaking')
                break
            self.check_combat()
            now = time.time()
            current_resonance = self.current_resonance()
            if not self.resonance_available(current_resonance):
                self.logger.debug(f'click_resonance not available break')
                break
            self.logger.debug(f'click_resonance resonance_available click {current_resonance}')

            if now - last_click > 0.1:
                if send_click and (current_resonance == 0 or last_op == 'resonance'):
                    self.task.click()
                    last_op = 'click'
                    continue
                if current_resonance > 0 and self.resonance_available(current_resonance):
                    if resonance_click_time == 0:
                        clicked = True
                        resonance_click_time = now
                    last_op = 'resonance'
                    self.send_resonance_key()
                last_click = now
            if self.try_lib_big():
                break
            self.task.next_frame()
        if clicked:
            self.update_res_cd()
        return clicked

    def is_mid_air_attack_available(self):
        if self.is_cartethyia:
            box = self.task.box_of_screen_scaled(3840, 2160, 2298, 1997, 2361, 2022, name='inner_cartethyia_space', hcenter=True)
            cropped = box.crop_frame(self.task.frame)
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            mean_val = np.mean(gray)
            contrast_val = np.std(gray)
            self.logger.debug(f'cartethyia_space mean {mean_val} contrast {contrast_val}')
            return mean_val > 190 and contrast_val > 60
    
    def try_mid_air_attack(self, timeout=2):
        self.get_sword_buffs()
        if self.liberation_available() or all(self.buffs.values()) or self.try_mid_air_attack_once:
            pass
        else:
            return
        if self.is_mid_air_attack_available():
            self.logger.info('perform mid-air attack')
            start = time.time()
            while True:
                self.task.send_key('SPACE', interval=0.1)
                self.sleep(0.01)
                self.task.click(interval=0.1)
                self.sleep(0.01)
                if not self.is_mid_air_attack_available():
                    self.sleep(0.5)
                    break
                if time.time() - start > timeout:
                    break
        elif self.try_mid_air_attack_once:
            start = time.time()
            while time.time() - start < 0.8:
                self.task.send_key('SPACE', interval=0.1)
                self.sleep(0.01)
                self.task.click(interval=0.1)
                self.sleep(0.01)
        self.try_mid_air_attack_once = False
    
    def is_small(self):
        if self.template_shape != self.task.frame.shape[:2]:
            self.init_template()
        self.is_cartethyia = bool(self.task.find_one(template=self.sword3_half_mat,
                                                     box=self.sword3_half_box, threshold=0.5))
        return self.is_cartethyia
    
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if not self.is_cartethyia:
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)

    def try_lib_big(self):
        if self.is_lib_big_available():
            if self.click_liberation():
                self.is_cartethyia = True
                self.click_resonance()
                return True

    def is_lib_big_available(self):
        if big := self.task.find_one('lib_cartethyia_big'):
            self.logger.debug('lib cartethyia big available {}'.format(big.confidence))
            self._liberation_available = True
            return True

    def get_sword_buffs(self):
        self.buffs = {
            'sword1': bool(self.task.find_one('forte_cartethyia_sword1', threshold=0.9)),
            'sword2': bool(self.task.find_one('forte_cartethyia_sword2', threshold=0.9)),
            'sword3': bool(self.task.find_one('forte_cartethyia_sword3', threshold=0.9)),
        }
        self.logger.debug(f"buffs {self.buffs}")
        return self.buffs
    
    def acquire_missing_buffs(self):
        self.get_sword_buffs()
        if all(self.buffs.values()):
            return False
        if has_perform_action := not all(self.buffs[k] for k in ['sword2', 'sword3']):
            self.logger.info('acquire missing buffs')
        if not self.buffs.get('sword2'):
            template = self.task.get_feature_by_name('forte_cartethyia_sword2')
            h = template.mat.shape[0]
            half_mat = template.mat[:int(h * 0.5)]
            half_box = self.task.get_box_by_name('forte_cartethyia_sword2')
            half_box.height = (half_box.height + 1) // 2
            start = time.time()
            is_first_attempt = True
            while time.time() - start < 2.5:
                if self.task.find_one(template=half_mat, box=half_box, threshold=0.9):
                    break
                if is_first_attempt and self.current_tool() < 0.1:
                    is_first_attempt = False
                    self.task.wait_until(lambda: self.current_tool() > 0.1, time_out=2)
                    start = time.time()
                self.click(interval=0.1, after_sleep=0.01)
                self.check_combat()
                self.task.next_frame()
            self.logger.debug(f'sword2: click duration {time.time() - start}')
        res = False
        if not self.buffs.get('sword3'):
            res = self.click_resonance()[0]
            self.check_combat()
        if self.liberation_available():
            res and self.sleep(0.2)
        elif has_perform_action:
            return True
        if not self.buffs.get('sword1'):
            if not has_perform_action:
                self.logger.info('acquire missing buffs')
            self.task.mouse_down()
            start = time.time()
            while time.time() - start < 1.5:
                if self.task.find_one('forte_cartethyia_sword1', threshold=0.9):
                    break
                self.task.next_frame()
            self.task.mouse_up()
            self.check_combat()
            self.logger.debug(f'sword1: heavy_att duration {time.time() - start}')
        if not any(self.buffs.values()):
            self.try_mid_air_attack_once = True
        return not self.liberation_available()