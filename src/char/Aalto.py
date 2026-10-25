import time

from src.char.BaseChar import BaseChar


class Aalto(BaseChar):
    """Fast Aero support rotation.

    Aalto mainly wants quick Concerto generation: cast Mist Avatar early, use
    Liberation/Echo when available, then leave the field with his Outro ready.
    """

    FIELD_TIME_OUT = 4.5

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.4)
        self.wait_down()

        start = time.time()
        skill_used = self.click_resonance(send_click=True, time_out=1)[0]
        self.click_echo(time_out=0)
        liberated = self.click_liberation(send_click=True, wait_if_cd_ready=0)

        while self.time_elapsed_accounting_for_freeze(start) < self.FIELD_TIME_OUT:
            if self.is_con_full():
                break
            if not skill_used and self.resonance_available():
                skill_used = self.click_resonance(send_click=True, time_out=1)[0]
                continue
            if not liberated and self.liberation_available():
                liberated = self.click_liberation(send_click=True, wait_if_cd_ready=0)
                continue
            self.click(interval=0.1)
            self.sleep(0.05)

        self.switch_next_char()
