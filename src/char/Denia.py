from src.char.BaseChar import BaseChar


class Denia(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_f_on_switch = False

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.97)
            self.click_resonance()
            self.click_echo(time_out=0)
            if self.click_liberation():
                self.continues_normal_attack(2.9)
                self.click_resonance()
                self.click_liberation()
        else:
            if self.resonance_available() and self.click_resonance()[0]:
                pass
            if self.click_liberation():
                self.click_resonance()
            self.click_echo()
            
        self.switch_next_char()

    def must_switch(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name == 'char_chisa':
            return True
        return super().must_switch(current_char, has_intro, target_low_con)
