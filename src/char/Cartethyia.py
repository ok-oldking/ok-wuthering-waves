import time

from src.char.BaseChar import BaseChar, Priority


class Cartethyia(BaseChar):
    def __init__(self, *args, **kwargs):
        self.manifest_time = -1
        self.is_cartethyia = True
        super().__init__(*args, **kwargs)

    def reset_state(self):
        self.manifest_time = -1
        super().reset_state()

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        else:
            self.click_echo()
        if self.is_small():
            if self.click_liberation():
                self.is_cartethyia = False
                self.manifest_time = time.time() if self.manifest_time < 0 else self.manifest_time
        if self.click_resonance()[0]:
            pass
        else:
            start = time.time()
            time_out = 1.1 if self.is_small() else 1.6
            while time.time() - start < time_out:
                if self.try_lib_big():
                    return self.switch_next_char()
                self.click(interval=0.15)
                self.sleep(0.05)
        self.try_lib_big()
        self.switch_next_char()

    def is_small(self):
        self.is_cartethyia = False
        if self.task.find_one('forte_cartethyia_space'):
            self.is_cartethyia = True
        return self.is_cartethyia

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if not self.is_cartethyia:
            return Priority.MAX - 2
        return super().do_get_switch_priority(current_char, has_intro)

    def try_lib_big(self):
        if self.is_lib_big_available():
            if self.click_liberation():
                self.manifest_time = -1
                self.is_cartethyia = True
                self.click_resonance()
                return True

    def is_lib_big_available(self):
        if big := self.task.find_one('lib_cartethyia_big'):
            self.logger.debug('lib cartethyia big available {}'.format(big.confidence))
            self._liberation_available = True
            return True
