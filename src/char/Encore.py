import time

from src.char.BaseChar import BaseChar, Priority


class Encore(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_heavy = 0

    def do_perform(self):
        self.logger.debug(
            f'Encore_perform_{self.has_intro}_{self.echo_available()}_{self.resonance_available()}_{self.liberation_available()}')
        if self.click_liberation():
            self.n4()
            self.click_resonance()
            self.n4()
            self.task.right_click()
            self.sleep(0.4)
            self.n4()
            self.click_resonance()
            if self.is_forte_full():
                self.logger.info('Encore is_forte_full cast')
                self.sleep(2)
                self.heavy_attack()
                self.last_heavy = time.time()
        elif self.resonance_available():
            self.click_resonance()
        elif self.echo_available():
            self.click_echo(duration=1.5)
        else:
            self.logger.info('Encore nothing is available')
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if time.time() - self.last_heavy < 4:
            self.logger.info(
                f'switch priority MIN because heavy attack not finished')
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def n4(self):
        self.continues_normal_attack(2.5)
