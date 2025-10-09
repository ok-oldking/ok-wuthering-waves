import time

from src.char.BaseChar import BaseChar


class Galbrena(BaseChar):

    def do_perform(self):
        if self.has_intro:
            self.logger.debug('has_intro wait and heavy attack for 86F and dodge')
            self.task.mouse_down()
            self.sleep(1)
            if self.need_fast_perform():
                self.task.mouse_up()
                return self.switch_next_char()
            self.sleep(0.44)
            self.task.mouse_up()
            self.continues_right_click(0.6)
        elif self.flying():
            self.wait_down()
        self.click_echo(time_out=0)
        if self.is_forte_full() and not self.need_fast_perform():
            self.click_resonance()
            if self.click_liberation():
                self.continues_normal_attack(1)
        if self.check_res() and not self.need_fast_perform():
            self.click_liberation()
            start = time.time();
            while self.check_res() and time.time() - start < 10:
                if self.flying():
                    self.shorekeeper_auto_dodge()
                self.click(after_sleep=0.1)
                self.check_combat()
            return self.switch_next_char()
        self.continues_normal_attack(1)
        self.click_resonance()
        return self.switch_next_char()

    def check_res(self):
        if not self.task.in_team_and_world():
            return False       
        best = self.task.find_best_match_in_box(self.task.get_box_by_name('box_target_enemy_long'),
                                               ['has_target', 'no_target'],
                                               threshold=0.6)
        self.logger.debug(f'check res {best}')
        return best
        
    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)   