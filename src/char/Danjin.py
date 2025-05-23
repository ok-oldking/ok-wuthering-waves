from src.char.BaseChar import BaseChar


class Danjin(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.bullets = 0

    def count_resonance_priority(self):
        return 0

    def do_perform(self):
        self.click_liberation()
        if self.is_forte_full():
            self.heavy_attack()
            self.sleep(0.2)
        elif self.click_echo():
            pass
        else:
            self.send_resonance_key()
        self.switch_next_char()
