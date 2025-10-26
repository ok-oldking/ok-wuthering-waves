import time, cv2
import numpy as np
from src.char.BaseChar import BaseChar, Priority, forte_white_color


class Cartethyia(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_cartethyia = True
        self.buffs = {'sword1': None, 'sword2': None, 'sword3': None}
        self.template_shape = None
        self.try_mid_air_attack_once = False
        self.transform = False
        self.res_time = -1
        self.n4_time = -1
        self.init_template()
        self.last_echo_time = -1
        self.echo_nudge_window = 0.6

    def _is_control_mode(self):
        is_control = bool(getattr(self.task, 'control', False))
        if callable(getattr(self.task, 'is_control_mode', None)):
            is_control = is_control or bool(self.task.is_control_mode())
        sel = getattr(self.task, 'selected_tool', None) or getattr(self.task, 'explore_mode', None) \
            or getattr(self.task, 'navigator_mode', None)
        if isinstance(sel, str):
            is_control = is_control or (sel.lower() == 'control')
        return is_control
    
    def _is_glide_mode_selected(self):
        # 탐색도구에서 ‘활공’이 선택되어 있는지 최대한 관용적으로 판정
        flags = [
            getattr(self.task, 'glide', None),
            getattr(self.task, 'is_glide_selected', None),
        ]
        for f in flags:
            if isinstance(f, bool) and f:
                return True
            if callable(f):
                try:
                    if bool(f()):
                        return True
                except Exception:
                    pass
        # 문자열 기반 모드 이름
        sel = getattr(self.task, 'selected_tool', None) or getattr(self.task, 'explore_mode', None) \
              or getattr(self.task, 'navigator_mode', None)
        if isinstance(sel, str) and ('glide' in sel.lower() or '활공' in sel):
            return True
        return False
    
    def nudge_after_echo_for_glide(self, max_time=0.35):
        """
        어린 모드 & (탐색도구=활공) & control 아님 & 에코 직후인 경우,
        짧은 입력을 넣어 Q 직후 ‘멍때림’ 공백을 제거.
        - 공중/지상 불문: SPACE 1~2틱 + click로 즉시 전투 재진입 유도
        - 너무 강하지 않게 0.35s 내로만 수행
        """
        if self._is_control_mode():
            return
        if not self._is_glide_mode_selected():
            return
        if not self.is_small():
            return
        if self.last_echo_time < 0 or time.time() - self.last_echo_time > self.echo_nudge_window:
            return

        start = time.time()
        self.logger.debug('nudge_after_echo_for_glide: begin')
        # 지상/공중 관계없이 아주 짧게 SPACE+click로 상태머신을 깨워줌
        while time.time() - start < max_time:
            self.task.send_key('SPACE', after_sleep=0.05)
            self.task.click(after_sleep=0.05)
            self.check_combat()
            self.task.next_frame()
        self.sleep(0.05, False)
        self.logger.debug('nudge_after_echo_for_glide: end')
    
    @property
    def intro_motion_freeze_duration(self):
        return 0.6 if self.is_cartethyia else 0.78

    @intro_motion_freeze_duration.setter
    def intro_motion_freeze_duration(self, _):
        pass

    def init_template(self):
        self.template_shape = self.task.frame.shape[:2]
        template = self.task.get_feature_by_name('forte_cartethyia_sword3')
        original_mat = template.mat
        h = original_mat.shape[0]
        self.sword3_half_mat = original_mat[:int(h * 0.5)]
        target_box = self.task.get_box_by_name('forte_cartethyia_sword3')
        target_box.height = int(h * 0.6)
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
        self.transform = False
        if self.has_intro:
            self.continues_normal_attack(1.2)
        else:
            _res = self.click_echo(time_out=0)
            try:
                _clicked = bool(_res[0]) if isinstance(_res, (tuple, list)) else bool(_res)
            except Exception:
                _clicked = bool(_res)
        if _clicked:
            self.last_echo_time = time.time()
            # NEW: 탐색도구=활공 선택 시에만, 에코 직후 복귀 보정
            self.nudge_after_echo_for_glide()

        if self.is_small():
            self.logger.info(f'is cartethyia')
            self.wait_down()
            if self.acquire_missing_buffs():
                return self.switch_next_char()
            self.check_combat()
            self.try_mid_air_attack()
            self.check_combat()
            if self.click_liberation():
                self.is_cartethyia = False
                self.last_res = -1
                self.transform = True
            elif not self.is_small():
                self.transform = True
        else:
            self.logger.info(f'is fleurdelys')
        if self.click_resonance_with_lib_big():
            pass
        else:
            time_out = 1.1 if self.is_small() else self.fleurdelys_n4_duration()
            start = time.time()
            while time.time() - start < time_out:
                if self.try_lib_big():
                    return self.switch_next_char()
                self.click_with_interval()
                self.check_combat()
                self.task.next_frame()
            self.n4_time = time.time()
        self.try_lib_big()
        self.switch_next_char()

    def fleurdelys_n4_duration(self):
        if not self.transform and self.has_intro:
            duration = 3.9 - (time.time() - self.last_perform)
        elif self.transform or self.is_first_engage() or \
                self.time_elapsed_accounting_for_freeze(self.n4_time, intro_motion_freeze=True) < 1.5:
            duration = 3.25
        elif (backswing := self.time_elapsed_accounting_for_freeze(self.res_time, intro_motion_freeze=True)) < 2.5:
            duration = 2 + max(0, 1.6 - backswing)
        else:
            duration = 1.9 - (time.time() - self.last_perform)
        self.n4_time = -1
        self.res_time = -1
        self.logger.debug(f'fleurdelys_n4_duration {duration}')
        return duration

    def click_resonance_with_lib_big(self):
        if self.time_elapsed_accounting_for_freeze(self.last_res) < self.res_cd:
            return False
        clicked = False
        self.logger.debug(f'click_resonance start')
        last_click = 0
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
            if not self.resonance_available():
                self.logger.debug(f'click_resonance not available break')
                break
            self.logger.debug(f'click_resonance resonance_available click {current_resonance}')

            if now - last_click > 0.1:
                if current_resonance > 0 and self.resonance_available():
                    if current_resonance < 0.17 and time.time() - resonance_click_time < 2.5:
                        self.click()
                        continue
                    if resonance_click_time == 0:
                        clicked = True
                        resonance_click_time = now
                    self.send_resonance_key()
                last_click = now
            if self.try_lib_big():
                break
            self.task.next_frame()
        if clicked:
            self.update_res_cd()
            self.res_time = time.time()
        return clicked

    def is_mid_air_attack_available(self):
        if self.is_cartethyia:
            box = self.task.box_of_screen_scaled(3840, 2160, 2298, 1997, 2361, 2022, name='inner_cartethyia_space',
                                                 hcenter=True)
            self.task.draw_boxes(box.name, box)
            if self.task.calculate_color_percentage(forte_white_color, box) > 0.15:
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
                self.task.send_key('SPACE', after_sleep=0.1)
                self.task.click(after_sleep=0.1)
                if not self.is_mid_air_attack_available():
                    self.sleep(0.4)
                    break
                if time.time() - start > timeout:
                    break
                self.sleep(0.1)
        elif self.try_mid_air_attack_once:
            start = time.time()
            while time.time() - start < 0.8:
                self.task.send_key('SPACE', after_sleep=0.1)
                self.task.click(after_sleep=0.1)
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
            half_box.height = int(h * 0.6)
            time_out = 3.5
            if try_once := bool(self.task.find_one(template=half_mat, box=half_box, threshold=0.85)):
                time_out = 2 if not self.is_first_engage() else 2.5
            start = time.time()
            interrupt_handled = False
            while time.time() - start < time_out:
                if not try_once and self.task.find_one(template=half_mat, box=half_box, threshold=0.85):
                    break
                if not interrupt_handled and self.current_tool() < 0.1:
                    time_out = 2.5 if time_out == 2 else time_out
                    interrupt_handled = True
                    self.task.wait_until(lambda: self.current_tool() > 0.1, time_out=3)
                    start = time.time()
                self.click(interval=0.1, after_sleep=0.01)
                self.check_combat()
                self.task.next_frame()
            self.logger.debug(f'sword2: click duration {time.time() - start}')
        res = False
        if not self.buffs.get('sword3'):
            _res = self.click_resonance()
+           try:
+               res = bool(_res[0]) if isinstance(_res, (tuple, list)) else bool(_res)
+           except Exception:
+               res = bool(_res)
            self.check_combat()
            if res:
                self.last_echo_time = time.time()
                # NEW: 탐색도구=활공 선택 시에만, 에코 직후 복귀 보정
                self.nudge_after_echo_for_glide()
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
