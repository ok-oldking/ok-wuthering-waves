from src.char.BaseChar import BaseChar


class Jianxin(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        self.click_liberation()
        if self.is_forte_full():
            self.heavy_attack(5.6)
        if self.resonance_available():
            self.click_resonance()
        if self.echo_available():
            self.click_echo(duration=0.8)
        self.switch_next_char()
