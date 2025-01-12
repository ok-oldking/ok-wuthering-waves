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

    def switch_out(self):
        super().switch_out()
        self.last_resonance = 0

    def do_perform(self):
        if self.has_intro:
            elapsed = self.time_elapsed_accounting_for_freeze(self.liberation_time)
            self.logger.debug(f'encore wait intro {elapsed}')
            if 6 < elapsed < 10 and self.is_forte_full():
                self.logger.debug('encore heavy attack after intro')
                self.task.mouse_down()
                self.wait_intro(time_out=1.4, click=False)
                self.task.mouse_up()
                self.sleep(0.1)
                self.last_heavy = time.time()
                return self.switch_next_char()
            else:
                self.wait_intro(time_out=1.4, click=True)
        if self.still_in_liberation():
            self.n4()
            return self.switch_next_char()
        if self.click_resonance()[0]:
            if not self.can_resonance_step2(delay=4):
                self.last_resonance = time.time()
                return self.switch_next_char()
        if self.click_liberation(wait_if_cd_ready=0.4):
            self.liberation_time = time.time()
            self.n4()
            return self.switch_next_char()
        else:
            self.logger.info('Encore nothing is available')
        if self.echo_available():
            self.logger.debug('click_echo')
            self.click_echo()
            return self.switch_next_char()
        self.switch_next_char()

    def count_liberation_priority(self):
        return 40

    def count_resonance_priority(self):
        return 40

    def count_echo_priority(self):
        return 40

    def can_resonance_step2(self, delay=2):
        return self.time_elapsed_accounting_for_freeze(self.last_resonance) < delay

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        self.logger.debug(
            f'encore last heavy time {self.last_heavy} {self.time_elapsed_accounting_for_freeze(self.last_heavy)}')
        if self.time_elapsed_accounting_for_freeze(self.last_heavy) < 4.6:
            return Priority.MIN
        elif self.still_in_liberation() or self.can_resonance_step2():
            self.logger.info(
                f'switch priority MAX because still in liberation')
            return Priority.MAX + 1
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def n4(self, duration=2.0):
        duration = 2.7 if self.click_resonance()[0] else 2.4
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
