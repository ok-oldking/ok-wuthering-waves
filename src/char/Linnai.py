import time

from src.char.BaseChar import BaseChar, forte_white_color, Priority

class Linnai(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0
        self.attribute = 0

    def do_perform(self):
        self.decide_teammate()
        if self.has_intro:
            if self.check_res():
                self.continues_normal_attack(1.33)
            else:
                self.continues_normal_attack(1)
                self.task.mouse_down()      
                self.click_echo(time_out=0)
                if self.task.wait_until(self.is_mouse_forte_full, time_out=2) and \
                     self.task.wait_until(lambda: not self.is_mouse_forte_full(), time_out=2.5):
                    self.task.mouse_up()
                    self.sleep(0.4)                 
                    self.perform_under_intro()
                else:
                    self.task.mouse_up()
                
        else: 
            self.click_echo(time_out=0)
            if self.perform_under_intro():
                pass
            elif self.flying():
                self.continues_normal_attack(0.1)
            elif not self.is_con_full() and self.click_liberation():
                self.continues_normal_attack(0.5)
            self.click_resonance()
        return self.switch_next_char()
            
    def perform_under_intro(self):
        if not self.check_res():
            self.logger.debug(f'Linnai fails entering accelerate mode!')
            return False
        self.task.wait_until(lambda: self.is_color_full() or self.is_con_full(), post_action=self.click,
                                     time_out=1)
        self.task.wait_until(lambda: not self.is_forte_full(),
             post_action=self.task.jump, time_out=3)

        if self.click_resonance()[0]:
            self.sleep(0.3) 
        self.wait_down()
        if not self.is_con_full() and self.click_liberation():
            self.task.wait_until(self.is_con_full, post_action=self.click, time_out=1.2) 
        return True

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

#    def combo_limit(self):
#        return self.time_elapsed_accounting_for_freeze(self.last_heavy) < 20

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        self.decide_teammate()
        if self.attribute == 2 and has_intro and current_char.char_name in {'char_moning'}:
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro)
        
    def decide_teammate(self):
        from src.char.Mornye import Mornye
        if self.attribute > 0:
            return
        if self.task.has_char(Mornye):
            self.attribute = 2
        else:
            self.attribute = 1