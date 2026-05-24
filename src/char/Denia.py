from src.char.BaseChar import BaseChar


class Denia(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_f_on_switch = False
        self.is_black_form = False

    def reset_state(self):
        super().reset_state()
        self.is_black_form = False

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.97)
        if not self.is_black_form:
            if self.resonance_available() and self.click_resonance()[0]:
                pass
            self.click_echo()
            if self.click_liberation():
                self.is_black_form = True  # fall-through to black form below
        if self.is_black_form:
            self.click_echo()
            if not self.liberation_available() and self.has_intro:
                self.continues_normal_attack(2.9)
            if self.resonance_available() and self.click_resonance()[0]:
                pass
            if self.click_liberation():
                self.is_black_form = False
        self.switch_next_char()

    def must_switch(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name == 'char_chisa':
            return True
        return super().must_switch(current_char, has_intro, target_low_con)
