from src.char.BaseChar import BaseChar


class Encore(BaseChar):
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
        elif self.resonance_available():
            self.click_resonance()
        elif self.echo_available():
            self.click_echo(duration=1.5)
        elif self.is_forte_full():
            self.heavy_attack()
        else:
            logger.info('Encore nothing is available')
        self.switch_next_char()

    def n4(self):
        self.continues_normal_attack(2.5)
