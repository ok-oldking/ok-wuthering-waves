from src.char.BaseChar import Priority
from src.char.Healer import Healer


class Douling(Healer):

    def do_perform(self):

        self.continues_normal_attack(1.2)
        self.click_resonance(send_click=False, time_out=0)
        self.continues_normal_attack(1.0)
        self.task.jump()
        self.continues_normal_attack(0.5)
        self.sleep(0.05)
        self.heavy_attack(2.5)
        self.click_echo(time_out=0)
        self.sleep(0.2)
        self.click_liberation(wait_if_cd_ready=False)
        self.switch_next_char()

    def switch_next_char(self, *args, **kwargs):
        if not self.is_con_full():
            self.continues_normal_attack(1.2)
        return super().switch_next_char(*args, **kwargs)

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if self.last_switch_time > 0 and self.time_elapsed_accounting_for_freeze(self.last_switch_time) < 20:
            return Priority.MIN
        return super().do_get_switch_priority(current_char, has_intro, target_low_con)
