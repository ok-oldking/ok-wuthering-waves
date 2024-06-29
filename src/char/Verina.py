from src.char.BaseChar import BaseChar, Priority


class Verina(BaseChar):

    def do_perform(self):
        if self.flying():
            return self.switch_next_char()
        self.click_liberation()
        if not self.click_resonance()[0]:
            self.click_echo()
            self.normal_attack()
            self.heavy_attack()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if has_intro:
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)
