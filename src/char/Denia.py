import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority


class Denia(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_2 = -1

    def reset_state(self):
        super().reset_state()
        self.lib_2 = -1

    def do_perform(self):
        if self.has_intro:
            self.wait_intro(1.2)
        duration = 1.6
        if self.time_elapsed_accounting_for_freeze(self.lib_2) > 20:
            duration = 10
            if self.has_intro:
                duration = 10
        elif self.has_intro:
            duration = 2.4
        if self.has_intro:
            self.continues_normal_attack(2)
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < duration:
            self.cycle_start()
            if self.click_resonance(time_out=0)[0]:
                pass
            elif self.click_echo(time_out=0):
                pass
            elif self.liberation_available():
                is_lib2 = self.task.find_one(Labels.denia_end_lib)
                if self.click_liberation(wait_if_cd_ready=0):
                    if is_lib2:
                        self.lib_2 = time.time()
                        self.click_echo(time_out=0)
                        break
                    else:
                        for i in range(16):
                            self.click(after_sleep=0.1)
                        # self.task.send_key('space')
                pass
            self.click()
            self.cycle_sleep()

        self.switch_next_char()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro:
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)
