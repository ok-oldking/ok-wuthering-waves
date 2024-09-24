from src.char.BaseChar import BaseChar, Priority


class Healer(BaseChar):

    def count_base_priority(self):
        return -1

    def count_echo_priority(self):
        return 0

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if has_intro and not target_low_con:
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro, target_low_con)
