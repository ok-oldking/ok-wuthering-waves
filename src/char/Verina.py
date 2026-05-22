from src.char.BaseChar import BaseChar


class Verina(BaseChar):
    res_cd = 20

    def can_switch(self, current_char=None, has_intro=False, target_low_con=False):
        if current_char and current_char.is_healer:
            return False
        if self.last_res > 0 and self.time_elapsed_accounting_for_freeze(self.last_res) < self.res_cd:
            return False

        time_elapsed = self.time_elapsed_accounting_for_freeze(self.last_perform)
        if time_elapsed >= 18:
            return True
        if has_intro and time_elapsed >= 12:
            return True

        return False
