from src.char.BaseChar import BaseChar, Priority


class Healer(BaseChar):

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if has_intro and not target_low_con:
            return Priority.MIN
        elif not self.resonance_available() and not self.liberation_available() and not target_low_con:
            return Priority.CURRENT_CHAR_PLUS
        else:
            return super().do_get_switch_priority(current_char, has_intro, target_low_con)
