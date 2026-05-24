import time

from src.char.BaseChar import BaseChar


class Verina(BaseChar):
    HEAVY_ATTACK_INTERVAL = 8

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = -1

    def can_heavy_attack(self):
        return self.time_elapsed_accounting_for_freeze(self.last_heavy) >= self.HEAVY_ATTACK_INTERVAL

    def do_perform(self):
        self.cycle_time_out = 0.4
        self.cycle_intro_time = 1
        self.cycle()

    def do_cycle(self):
        if self.is_con_full():
            return False
        elif self.click_liberation(wait_if_cd_ready=False):
            return True
        elif self.click_resonance(send_click=True, time_out=0)[0]:
            return True
        elif self.click_echo(time_out=0):
            return True
        elif self.is_mouse_forte_full() and self.can_heavy_attack():
            self.heavy_attack(0.7)
            self.last_heavy = time.time()
            return False
        else:
            self.click()
            return True
