import time

from src.char.BaseChar import BaseChar, SwitchPriority, forte_white_color

class Linnai(BaseChar):
    CON_READY_TO_SWITCH = 0.99

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0

    def do_perform(self):
        if self.has_intro:
            if self.is_con_ready_to_switch():
                return self.switch_next_char()
            if self.check_res():
                self.continues_normal_attack(1.33, until_con_full=True)
            else:
                self.continues_normal_attack(1, until_con_full=True)
                if self.is_con_ready_to_switch():
                    return self.switch_next_char()
                self.click_echo(time_out=0)
                if not self.is_con_ready_to_switch():
                    self.click_liberation()
                if self.is_con_ready_to_switch():
                    return self.switch_next_char()
                if not self.is_mouse_forte_full():
                    self.click_resonance()
                if self.is_con_ready_to_switch():
                    return self.switch_next_char()
                self.task.wait_until(lambda: self.is_mouse_forte_full() or self.is_con_ready_to_switch(),
                                     post_action=self.click, time_out=2)
                if self.is_con_ready_to_switch():
                    return self.switch_next_char()
                self.task.mouse_down() 
                if self.task.wait_until(lambda: not self.is_mouse_forte_full(), time_out=5):
                    self.task.mouse_up()
                    self.sleep(0.4)                 
                    self.perform_under_intro()
                else:
                    self.task.mouse_up()
                
        else: 
            self.click_echo(time_out=0)
            if self.is_con_ready_to_switch():
                pass
            elif self.perform_under_intro():
                pass
            elif self.flying():
                self.continues_normal_attack(0.1)
            elif not self.is_con_ready_to_switch() and self.click_liberation():
                self.continues_normal_attack(0.5, until_con_full=True)
            if not self.is_con_ready_to_switch():
                self.click_resonance()
        return self.switch_next_char()
            
    def perform_under_intro(self):
        if not self.check_res():
            self.logger.debug(f'Linnai fails entering accelerate mode!')
            return False
        self.task.wait_until(lambda: self.is_color_full() or self.is_con_ready_to_switch(), post_action=self.click,
                                     time_out=1)
        if self.is_con_ready_to_switch():
            return True
        if self.task.wait_until(lambda: not self.is_forte_full() or self.is_con_ready_to_switch(),
             post_action=self.task.jump, time_out=3):
            if self.is_con_ready_to_switch():
                return True
            if self.task.wait_until(lambda: self.is_con_ready_to_switch() or self.click_resonance()[0],
             post_action=self.click, time_out=2):
                if self.is_con_ready_to_switch():
                    return True
                self.wait_after_resonance_kick()
                second_kick = False

                def click_second_resonance():
                    nonlocal second_kick
                    if self.is_con_ready_to_switch():
                        return True
                    second_kick = self.click_resonance()[0]
                    return second_kick

                self.task.wait_until(click_second_resonance, post_action=self.click, time_out=3)
                if second_kick:
                    self.wait_after_resonance_kick()
        if not self.is_con_ready_to_switch() and self.click_liberation():
            self.task.wait_until(self.is_con_ready_to_switch, post_action=self.click_with_interval, time_out=1.2)
        return True

    def is_con_ready_to_switch(self):
        return self.get_current_con() >= self.CON_READY_TO_SWITCH

    def wait_after_resonance_kick(self):
        self.sleep(0.3)
        self.wait_down()

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

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_moning'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
