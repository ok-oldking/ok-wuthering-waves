from src.char.BaseChar import BaseChar, WWRole

class HavocRover(BaseChar):
    def count_base_priority(self):
        return super().count_base_priority() + 1
    def count_liberation_priority(self):
        return super().count_liberation_priority() + 5
    def do_perform(self):
        if self.has_intro:
            self.wait_down()
        if self.is_forte_full() and not self.resonance_available():
            self.wait_down()
            self.heavy_attack()
            self.sleep(0.4)
            if self.role == WWRole.MainDps:
                self.continues_normal_attack(duration=3)
            if self.click_liberation():
                if self.click_echo():
                    return self.switch_next_char()
        if self.click_resonance()[0]:
            return self.switch_next_char()
        self.click_liberation()
        self.click_echo()
        self.switch_next_char()

    #def sub_dps(self):
    #    if self.liberation_available():
    #        self.click_liberation()
    #        if self.echo_available():
    #            self.click_echo()
    #            self.switch_next_char()
    #    if self.click_resonance()[0]:
    #        return self.switch_next_char()
    #    
    #    if self.is_forte_full():
    #        self.wait_down()
    #        self.heavy_attack()
    #        self.sleep(0.4)
    #        if self.click_resonance()[0]:
    #            return self.switch_next_char()
    #    if self.echo_available():
    #        self.click_echo()
    #    self.switch_next_char()