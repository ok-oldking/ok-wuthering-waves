import time

from src.char.BaseChar import BaseChar, Priority


class Encore(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_heavy = 0
        self.liberation_time = 0
        self.last_resonance = 0

    def still_in_liberation(self):
        return self.time_elapsed_accounting_for_freeze(self.liberation_time) < 9.5

    def do_perform(self):
        target_low_con = False
        if self.has_intro:
            self.logger.debug('encore wait intro')
            self.continues_normal_attack(.8)
            self.wait_down()
        else:
            while not self.still_in_liberation() and self.can_resonance_step2():
                if self.click_resonance()[0]:
                    self.last_resonance = 0
                    self.logger.info('try Encore resonance_step2 success')
                    self.sleep(0.2)
                    break
                else:
                    self.task.next_frame()
        if self.still_in_liberation():
            target_low_con = True
            self.n4()
        elif self.click_resonance()[0]:
            self.logger.debug('click_resonance')
            self.last_resonance = time.time()
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

    def can_resonance_step2(self, delay=2):
        return self.time_elapsed_accounting_for_freeze(self.last_resonance) < delay

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if self.time_elapsed_accounting_for_freeze(self.last_heavy) < 4:
            return Priority.MIN
        elif self.still_in_liberation() or self.can_resonance_step2():
            self.logger.info(
                f'switch priority MAX because still in liberation')
            return Priority.MAX + 1
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def n4(self, duration=2.0):
        duration = 2.6 if self.click_resonance()[0] else 2.3
        if self.time_elapsed_accounting_for_freeze(self.liberation_time) < 6:
            self.logger.debug('encore liberation n4')
            self.continues_normal_attack(duration=duration)
        elif self.is_forte_full():
            self.heavy_attack()
            self.logger.debug('encore liberation heavy')
            self.last_heavy = time.time()
        else:
            self.logger.debug('encore liberation nothing to do')
            self.click_resonance()
