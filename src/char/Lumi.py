import time

from src.char.BaseChar import BaseChar


class Lumi(BaseChar):
    """Quick Electro support rotation alternating skill modes when possible."""

    FIELD_TIME_OUT = 5.0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.5)
        self.wait_down()

        start = time.time()
        self.click_echo(time_out=0)
        self.click_liberation(send_click=True, wait_if_cd_ready=0)

        while self.time_elapsed_accounting_for_freeze(start) < self.FIELD_TIME_OUT:
            if self.is_con_full() and self.time_elapsed_accounting_for_freeze(start) > 1.5:
                break
            if self.resonance_available():
                if self.click_resonance(send_click=True, time_out=1)[0]:
                    self.continues_normal_attack(0.4)
                    continue
            if self.is_mouse_forte_full():
                self.heavy_click_forte(self.is_mouse_forte_full)
                continue
            if self.liberation_available():
                self.click_liberation(send_click=True, wait_if_cd_ready=0)
                continue
            self.click(interval=0.1)
            self.sleep(0.05)

        self.switch_next_char()
