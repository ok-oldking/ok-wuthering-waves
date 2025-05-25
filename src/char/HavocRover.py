from src.char.BaseChar import BaseChar


class HavocRover(BaseChar):
    def do_perform(self):
        if self.has_intro:
            if self.is_forte_full():
                self.heavy_attack(0.8)
            else:
                self.continues_normal_attack(0.9)
        self.click_liberation(send_click=True)
        if self.click_resonance(send_click=True)[0]:
            return self.switch_next_char()
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_switch_time))
        self.switch_next_char()
