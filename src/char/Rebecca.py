import time

from src.char.BaseChar import BaseChar


class Rebecca(BaseChar):
    HMG_TIME = 5.2

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.0)
        elif self.flying():
            self.wait_down()

        self.click_echo(time_out=0)
        self.perform_enhanced_heavy()

        if self.click_resonance(time_out=0.8)[0]:
            self.continues_normal_attack(0.35)

        self.perform_enhanced_heavy()

        if not self.need_fast_perform() and self.click_liberation(wait_if_cd_ready=0):
            self.perform_hmg_mode()
            return self.switch_next_char()

        self.continues_normal_attack(0.7)
        self.switch_next_char()

    def perform_enhanced_heavy(self):
        if self.heavy_click_forte(self.is_forte_full):
            self.continues_normal_attack(0.25)
            return True
        return False

    def perform_hmg_mode(self):
        start = time.time()
        last_liberation = start
        while self.time_elapsed_accounting_for_freeze(start) < self.HMG_TIME:
            if self.need_fast_perform():
                return
            self.click(interval=0.08)
            now = time.time()
            if now - last_liberation > 0.9:
                self.send_liberation_key()
                last_liberation = now
            self.check_combat()
            self.task.next_frame()
