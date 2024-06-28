from src.char.BaseChar import BaseChar


class Verina(BaseChar):

    def do_perform(self):
        if self.flying():
            return self.switch_next_char()
        self.click_liberation()
        if not self.click_resonance()[0]:
            self.click_echo()
            self.heavy_attack()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if has_intro:
            return super().do_get_switch_priority(current_char, has_intro) - 5
        else:
            return super().do_get_switch_priority(current_char, has_intro) - 1
