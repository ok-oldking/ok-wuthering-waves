from src.char.BaseChar import BaseChar, Priority


class Healer(BaseChar):

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if isinstance(current_char, Healer):
            self.logger.debug(
                f'Healer do_get_switch_priority Healer to Healer set to MIN')
            return Priority.MIN
        elif self.time_elapsed_accounting_for_freeze(self.last_perform) > 20:
            self.logger.debug(
                f'Healer do_get_switch_priority 20 seconds since last switch')
            return Priority.SKILL_AVAILABLE * 2
        elif not has_intro and self.liberation_available() and self.resonance_available() and self.echo_available():
            self.logger.debug(
                f'Healer do_get_switch_priority everything available')
            return Priority.SKILL_AVAILABLE * 2
        else:
            return Priority.BASE_MINUS_1
