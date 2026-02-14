import time
from src.char.BaseChar import BaseChar


class Mornye(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.33)
        self.check_f_on_switch = True
        time_out = 10
        start = time.time()
        if not self.on_air():
            if self.combo_limit():
                self.logger.debug('perform quick actions')
                if not self.click_echo():
                    self.continues_normal_attack(0.1)
                return self.switch_next_char()
            self.logger.debug('not on_air start attacking')
            while time.time() - start < time_out and not self.on_air():
                self.click()
                self.click_resonance()
                self.check_combat()
                self.sleep(0.1)
                if self.is_mouse_forte_full():
                    self.heavy_attack()
                    self.sleep(0.3)
        else:
            self.logger.debug('already on_air')
        if self.on_air():
            self.logger.debug('on_air start attacking')
            self.click_liberation()
            start = time.time()
            time_out = 10
            while time.time() - start < time_out and not self.is_mouse_forte_full() and self.on_air():
                self.click()
                self.click_resonance()
                self.check_combat()
                self.sleep(0.1)
            if self.on_air() and self.is_mouse_forte_full():
                self.logger.debug('mouse forte full, heavy attack')
                if self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
                    self.last_heavy = time.time()
                    self.check_f_on_switch = False
        else:
            self.logger.debug('failed to jump on_air, switch next char')
        self.switch_next_char()

    def on_air(self):
        return self.has_long_action2()

    def on_combat_end(self, chars):
        self.switch_other_char()

    def combo_limit(self):
        return self.time_elapsed_accounting_for_freeze(self.last_heavy) < 20
