import time

from src.char.BaseChar import BaseChar, Priority


class Changli(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.enhanced_normal = False
        self.last_e = 0

    def reset_state(self):
        self.enhanced_normal = False

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if time.time() - self.last_e < 3:
            self.logger.info(
                f'switch priority MIN because e not finished')
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def do_perform(self):
        # self.logger.debug(
        #     f'Encore_perform_{self.has_intro}_{self.echo_available()}_{self.resonance_available()}_{self.liberation_available()}')
        if self.has_intro or self.enhanced_normal:
            self.normal_attack()
            self.sleep(0.5)
        self.enhanced_normal = False
        if self.is_forte_full():
            self.heavy_attack(0.8)
            return self.switch_next_char()
        if self.click_liberation():
            self.heavy_attack(0.8)
            return self.switch_next_char()
        elif self.resonance_available():
            self.send_resonance_key()
            self.enhanced_normal = True
        elif self.click_echo(1.5):
            pass
        else:
            self.normal_attack()
            self.logger.info('Changli nothing is available')
        self.switch_next_char()
