from src.char.Healer import Healer
import time
from src.char.BaseChar import BaseChar, Priority

class Moning(Healer):

    def do_perform(self):
        time_out = 10
        start = time.time()
        if not self.on_air():
            self.logger.debug('not on_air start attacking')
            while time.time() - start < time_out and not self.on_air():
                self.click()
                self.click_resonance()
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
            while time.time() - start < time_out and not self.is_mouse_forte_full():
                self.click()
                self.click_resonance()
                self.sleep(0.1)
            if self.is_mouse_forte_full():
                self.logger.debug('mouse forte full, heavy attack')
                self.heavy_attack()
        else:
            self.logger.debug('failed to jump on_air, switch next char')
        self.switch_next_char()

    def on_air(self):
        return self.has_long_action2()

    def on_combat_end(self, chars):
        self.switch_other_char()

    def do_get_switch_priority(self,current_char:BaseChar,has_intro=False, target_low_con=False):
        if self.liberation_available:
            return Priority.MAX
        if current_char.is_con_full():
            return super().do_get_switch_priority(current_char, True)
        return Priority.MIN

