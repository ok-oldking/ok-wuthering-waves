import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority


class Denia(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_2 = -1
        self.lib_1_casted = False

    def reset_state(self):
        super().reset_state()
        self.lib_2 = -1
        self.lib_1_casted = False

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(2)
        elif self.lib_1_casted:
            self.continues_normal_attack(1.3)
        duration = 1.2
        if self.lib_1_casted:
            duration = 4.4
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < duration:
            self.cycle_start()
            if self.time_elapsed_accounting_for_freeze(self.lib_2) < 10 and self.is_con_full():
                return self.switch_next_char()
            if self.click_resonance()[0]:
                pass
            elif self.liberation_available():
                is_lib2 = self.task.find_one(Labels.denia_end_lib)
                if self.click_liberation(wait_if_cd_ready=0):
                    if is_lib2:
                        self.lib_2 = time.time()
                        self.lib_1_casted = False
                        self.click_echo(time_out=0)
                        return self.switch_next_char()
                    else:
                        self.lib_1_casted = True
                        # for i in range(12):
                        #     self.click(after_sleep=0.1)
                        # self.task.send_key('space')
                        # for i in range(12):
                        #     self.click(after_sleep=0.1)
                        # self.click_resonance()
                        # self.click(after_sleep=0.1)
                        self.continues_normal_attack(1.9)
                        return self.switch_next_char()
                pass
            else:
                self.click()
            self.cycle_sleep()

        self.switch_next_char()

    # def click_resonance(self, **kwargs):
    #     if self.task.find_one(Labels.denia_lib2):
    #         return super().click_resonance()
    #     else:
    #         return [False]
    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro:
            return SwitchPriority.NO
        elif self.has_buff():
            return SwitchPriority.LOW
        else:
            return super().get_switch_priority(current_char, has_intro, target_low_con)
