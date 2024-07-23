import time

from src.char.BaseChar import BaseChar, Priority


class Encore(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_heavy = 0
        self.liberation_time = 0
        self.last_resonance = 0

    def still_in_liberation(self):
        return time.time() - self.liberation_time < 10

    def do_perform(self):
        target_low_con = False
        if self.has_intro:
            self.continues_normal_attack(.7)
            self.wait_down()
        elif self.can_resonance_step2(4):
            if self.click_resonance()[0]:
                self.logger.info('try Encore resonance_step2 success')
                self.sleep(0.3)
            else:
                self.task.wait_until(self.resonance_available, time_out=1)
                wait_success = self.click_resonance()[0]
                self.logger.info(f'try Encore resonance_step2 wait_success:{wait_success}')

        if self.still_in_liberation():
            target_low_con = True
            self.n4()
        elif self.click_resonance()[0]:
            self.logger.debug('click_resonance')
            self.last_resonance = time.time()
            pass
        elif self.click_liberation():
            self.liberation_time = time.time()
            self.n4()
            target_low_con = True
        elif self.echo_available():
            self.logger.debug('click_echo')
            self.click_echo(duration=1.5)
        else:
            self.logger.info('Encore nothing is available')
        self.switch_next_char(target_low_con=target_low_con)

    def count_liberation_priority(self):
        return 40

    def count_resonance_priority(self):
        return 40

    def count_echo_priority(self):
        return 40

    def can_resonance_step2(self, delay=3):
        return time.time() - self.last_resonance < delay

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if time.time() - self.last_heavy < 3:
            return Priority.MIN
        elif self.still_in_liberation() or self.can_resonance_step2():
            self.logger.info(
                f'switch priority MIN because still in liberation')
            return Priority.MAX + 1
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def n4(self, duration=2.0):
        duration = 2.6 if self.click_resonance()[0] else 2.3
        if time.time() - self.liberation_time < 6 or not self.is_forte_full():
            self.continues_normal_attack(duration=duration)
            if not self.still_in_liberation():
                self.click_resonance()
        else:
            self.heavy_attack()
            self.logger.info('encore heavy')
            self.last_heavy = time.time()
