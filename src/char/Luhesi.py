import time

from src.char.BaseChar import BaseChar, Priority


class Luhesi(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_intro = -1

    def do_perform(self):            
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if self.luhesi_lib_available() and self.click_liberation(wait_if_cd_ready=0):
            self.f_break()
            return True

    def luhesi_lib_available(self):
        return self.available('luhesi_lib', check_cd=False) and not self.has_cd('liberation')

    def perform_everything(self):
        self.continues_normal_attack(1.1)
        if not self.has_intro:
            self.send_resonance_key(post_sleep=0.1)
            return
        else:
            self.last_intro = time.time()
        if not self.flying():
            self.task.wait_until(self.flying, post_action=self.task.jump, time_out=0.2)
        self.logger.debug(f"detect {self.available('echo', check_color=True)}")
        detect_ready = self.echo_available()
        start = time.time()
        res_count = 0
        try_jump = False
        while self.time_elapsed_accounting_for_freeze(start) < 12:
            if self.detect_elbow_strike(detect_ready):
                self.logger.debug("Detected an elbow strike, attempting to reset.")
                self.task.wait_until(lambda: not self.detect_elbow_strike(detect_ready), 
                                     post_action=lambda: self.continues_right_click(0.05), time_out=1.5)
            elif self.handle_heavy(res_count) and res_count > 2:
                self.lib()
                return
            elif try_jump and not self.check_res():
                self.task.wait_until(lambda: self.task.find_one('luhesi_kick', threshold=0.7) or\
                                             self.detect_elbow_strike(detect_ready),
                                             post_action=self.send_resonance_key, time_out=1)
                if self.detect_elbow_strike(detect_ready):
                    continue
                try_jump = False
                if self.task.find_one('luhesi_kick', threshold=0.7):
                    res_count+=1
                else:
                    if res_count == 2:
                        self.wait_down()
                    self.lib()
                    return
            elif self.check_res():
                self.task.jump()
                try_jump = True
            else:
                self.click()
            self.sleep(0.01)

    def handle_heavy(self, res_count):
        start = time.time()
        have_kick = False
        while self.task.find_one('luhesi_kick', threshold=0.7) and time.time() - start < 3:
            if not have_kick:
                self.logger.debug('handle special attack')
            have_kick = True           
            if res_count < 3:
                self.f_break()
            self.click(after_sleep=0.1)
        return have_kick

    def check_res(self):
        if not self.task.in_team_and_world():
            return False
        best = self.task.find_best_match_in_box(self.task.get_box_by_name('target_box_long2'),
                                               ['has_target', 'no_target'],
                                               threshold=0.6)
        self.logger.debug(f'check res {best}')
        return best
        
    def detect_elbow_strike(self, ready):
        return ready and not self.available('echo', check_color=True)
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        """24秒疑似吃的系统时间"""
        if time.time() - self.last_intro > 24 and has_intro:
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro)