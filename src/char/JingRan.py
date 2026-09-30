import time

from src.char.BaseChar import BaseChar


class JingRan(BaseChar):
    BUILD_TIMEOUT = 8
    YINGHUO_DURATION = 15

    def do_perform(self):
        # Kit reference: https://ww.nanoka.cc/character/1212/
        self.wait_intro()
        self.click_echo(time_out=0)

        start = time.time()
        liberation_start = None
        while self.time_elapsed_accounting_for_freeze(start) < self.BUILD_TIMEOUT + self.YINGHUO_DURATION:
            if liberation_start is None:
                if self.time_elapsed_accounting_for_freeze(start) >= self.BUILD_TIMEOUT:
                    break
            elif self.time_elapsed_accounting_for_freeze(liberation_start) >= self.YINGHUO_DURATION:
                break

            self.cycle_start()
            # Spend 300 Qi before liberation adds 200; each heavy also changes stance.
            if self.is_forte_full():
                self.heavy_click_forte()
            elif liberation_start is None and self.click_liberation(wait_if_cd_ready=0):
                liberation_start = time.time()
            elif self.click_resonance(send_click=False, time_out=1)[0]:
                # Normal attack chains the airborne skill follow-up, restoring 100 Qi.
                self.continues_normal_attack(0.8)
            else:
                self.click(interval=0.1)
            self.cycle_sleep()

        self.switch_next_char()
