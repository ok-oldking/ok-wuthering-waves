from src.char.BaseChar import BaseChar, Priority


class Healer(BaseChar):

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        return self.do_get_healer_switch_priority(current_char, has_intro, target_low_con)
