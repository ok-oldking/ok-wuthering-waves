from src.char.BaseChar import BaseChar, Priority


class Cartethyia(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        if self.is_small():
            self.click_liberation()
        if self.click_resonance()[0]:
            pass
        elif self.click_echo():
            pass
        else:
            self.continues_normal_attack(1.6)
        if self.try_lib_big():
            self.click_resonance()
        self.switch_next_char()

    def is_small(self):
        return self.task.find_one('forte_cartethyia_space')

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        return Priority.MAX - 2

    def try_lib_big(self):
        if self.is_lib_big_available():
            if self.click_liberation():
                self.click_resonance()
                return True

    def is_lib_big_available(self):
        if big := self.task.find_one('lib_cartethyia_big'):
            self.logger.debug('lib cartethyia big available {}'.format(big.confidence))
            self._liberation_available = True
            return True
