import time

from src.char.BaseChar import BaseChar


class Xiangliyao(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.liberation_time = 0

    def do_perform(self):
        if self.click_liberation():
            self.liberation_time = time.time()
        if self.still_in_liberation():
            while not self.click_resonance(send_click=True)[0]:
                self.continues_normal_attack(1)
        elif self.echo_available():
            self.logger.debug('click_echo')
            self.click_echo(duration=1.5)
        else:
            self.click_resonance(send_click=True)
        self.switch_next_char()

    def count_liberation_priority(self):
        return 40

    def count_base_priority(self):
        return super().count_base_priority() + 100 if self.still_in_liberation() and self.resonance_available() else 0

    def still_in_liberation(self):
        return self.time_elapsed_accounting_for_freeze(self.liberation_time) < 25
