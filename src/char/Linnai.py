import time

from src.char.BaseChar import BaseChar, forte_white_color

class Linnai(BaseChar):

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.33)
        elif self.flying():
            self.wait_down()
        self.click_echo(time_out=0)
        if not self.check_res():
            start = time.time()
            second = False
            self.task.wait_until(self.is_mouse_forte_full, post_action=self.click,
                                     time_out=2.5)
            if self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
                pass
            else:
                if self.liberation_available():
                    self.click_resonance()
                    self.sleep(0.6)
                if self.click_liberation():
                    self.continues_normal_attack(0.5)
                    return self.switch_next_char()
                self.click_resonance()
                return self.switch_next_char()
        self.click_liberation()
        self.task.wait_until(lambda: self.is_color_full() or self.is_con_full(), post_action=self.click,
                                     time_out=8)
        if self.is_color_full() and self.task.wait_until(lambda: not self.is_forte_full(),
                                     post_action=self.task.jump, time_out=3):
            self.click_resonance()
        self.switch_next_char()

    def check_res(self):
        if not self.task.in_team_and_world():
            return False
        best = self.task.find_best_match_in_box(self.task.get_box_by_name('target_box_long2'),
                                               ['has_target', 'no_target'],
                                               threshold=0.6)
        self.logger.debug(f'check res {best}')
        return best

    def is_color_full(self):
        box = self.task.box_of_screen_scaled(5120, 2880, 2846, 2602, 2889, 2690, name='color_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        self.logger.debug(f'forte_color_percent {white_percent}')
        return white_percent > 0.06

    def on_combat_end(self, chars):
        self.switch_other_char()
