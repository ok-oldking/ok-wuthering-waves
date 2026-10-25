import time

from src.char.BaseChar import BaseChar


class Lingyang(BaseChar):
    """Glacio main DPS placeholder with a bounded Striding Lion style loop."""

    FIELD_TIME_OUT = 8.0
    INTRO_ATTACK_TIME = 0.8
    POST_LIB_ATTACK_TIME = 1.0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(self.INTRO_ATTACK_TIME)
        self.wait_down()

        self.click_echo(time_out=0)
        if self.liberation_available():
            if self.click_liberation(send_click=True):
                self.continues_normal_attack(self.POST_LIB_ATTACK_TIME)

        self.perform_lion_cycle()
        self.switch_next_char()

    def perform_lion_cycle(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.FIELD_TIME_OUT:
            if self.is_con_full() and self.time_elapsed_accounting_for_freeze(start) > 2:
                break
            if self.is_mouse_forte_full():
                if self.heavy_click_forte(self.is_mouse_forte_full):
                    self.continues_normal_attack(0.4)
                continue
            if self.resonance_available():
                if self.click_resonance(send_click=True, time_out=1)[0]:
                    self.continues_normal_attack(0.35)
                    continue
            if self.liberation_available():
                self.click_liberation(send_click=True, wait_if_cd_ready=0)
                continue
            self.click(interval=0.1)
            self.sleep(0.05)
