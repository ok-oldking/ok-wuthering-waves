from src.char.BaseChar import BaseChar, Priority


class Healer(BaseChar):

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if not has_intro and self.liberation_available():
            self.logger.debug(
                f'Healer do_get_switch_priority everything available')
            return Priority.SKILL_AVAILABLE * 2
        else:
            return Priority.BASE_MINUS_1
        
