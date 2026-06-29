import time

from src.char.BaseChar import BaseChar, SwitchPriority
from src.char.TeamRotations import advance_cqc_phase, get_cqc_phase


class Qiuyuan(BaseChar):
    def do_perform(self):
        if self.cartethyia_qiuyuan_chisa_rotation():
            return
        if self.has_intro:
            self.continues_normal_attack(1.17)
        if self.flying():
            self.wait_down()            
        start = time.time()
        timeout = lambda: time.time() - start < 1.2
        if self.has_sub_dps_intro:
            timeout = lambda: time.time() - start < 4
        while timeout():        
            self.click_echo(time_out=0)
            if time.time() - start < 0.5 and self.click_liberation():              
                start = time.time()
            if self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
                return self.switch_next_char()
            if self.flying() and not self.is_mouse_forte_full():
                self.shorekeeper_auto_dodge()  
            self.click()
            self.check_combat()
            self.task.next_frame()
        self.click_resonance()
        self.switch_next_char()

    def cartethyia_qiuyuan_chisa_rotation(self):
        phase = get_cqc_phase(self.task)
        if phase is None:
            return False
        expected_char, action = phase
        if expected_char != self.__class__.__name__:
            self.switch_next_char()
            return True
        self.wait_down()
        getattr(self, action)()
        advance_cqc_phase(self.task)
        self.switch_next_char()
        return True

    def cqc_qiuyuan_aae_jump_a(self):
        self.continues_normal_attack(0.35)
        self.click_resonance(time_out=0.4)
        self.task.jump(after_sleep=0.05)
        self.continues_normal_attack(0.25)

    def cqc_qiuyuan_aae_jump_z(self):
        self.continues_normal_attack(0.35)
        self.click_resonance(time_out=0.4)
        self.task.jump(after_sleep=0.05)
        if self.is_mouse_forte_full():
            self.heavy_click_forte(check_fun=self.is_mouse_forte_full)
        else:
            self.heavy_attack(0.35)

    def cqc_qiuyuan_r(self):
        self.click_echo(time_out=0)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        phase = get_cqc_phase(self.task)
        if phase is not None:
            expected_char, _ = phase
            if expected_char == self.__class__.__name__:
                return SwitchPriority.MUST
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)
        
    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)
