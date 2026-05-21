from src.char.BaseChar import BaseChar


class Denia(BaseChar):

    def do_perform(self):
        if self.has_intro:
            self.wait_intro(1.2)

        performed = False
        if self.resonance_available() and self.click_resonance()[0]:
            performed = True
        if self.click_liberation():
            performed = True
        if self.echo_available() and self.click_echo():
            performed = True

        if not performed:
            self.continues_normal_attack(1.2)
        self.switch_next_char()
