import time

from src.char.BaseChar import BaseChar, SwitchPriority
from src.char.TeamRotations import advance_cqc_phase, get_cqc_phase, get_rotation_switch_priority, perform_rotation_phase


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
        return perform_rotation_phase(self, get_cqc_phase, advance_cqc_phase, wait_down=True)

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
        priority = get_rotation_switch_priority(self, get_cqc_phase)
        if priority is not None:
            return priority
        return super().get_switch_priority(current_char, has_intro, target_low_con)
        
    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)
