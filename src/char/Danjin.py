from src.char.BaseChar import BaseChar


class Danjin(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def count_resonance_priority(self):
        return 0

    def do_perform(self):
        liberated = self.click_liberation()
        if liberated:
            self.sleep(1.2)
            self.click_echo(time_out=2)
            return self.switch_next_char()
        if self.is_forte_full() and self.has_intro:
            duration = 0.8
            if self.task.debug:
                self.task.screenshot("danjin_heavy")
            self.heavy_attack(duration)
            self.sleep(0.2)
            self.normal_attack()
            self.sleep(0.1)
            return self.switch_next_char()
        if self.has_intro:
            self.continues_normal_attack(1.1)
        else:
            self.wait_down()
            self.continues_normal_attack(0.4, interval=0.1)
        self.continues_click(self.get_resonance_key(), 1.1, interval=0.2)
        self.switch_next_char()
