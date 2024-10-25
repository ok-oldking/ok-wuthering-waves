from src.char.BaseChar import BaseChar, WWRole

class Danjin(BaseChar):
    def count_resonance_priority(self):
        return 0
    def do_perform(self):
        if self.role == WWRole.SubDps:
            self.sub_dps()
        else: 
            self.click_liberation()
            if self.is_forte_full():
                self.heavy_attack()
                self.sleep(0.2)
            elif self.click_echo():
                pass
            else:
                self.task.send_key(self.get_resonance_key())
            self.switch_next_char()
    def sub_dps(self):
        if self.is_forte_full():
                self.heavy_attack()
                self.sleep(0.25)
                self.normal_attack()
        if self.liberation_available():
            self.click_liberation()
        if self.echo_available():
            self.click_echo()
            self.switch_next_char()

        self.continues_normal_attack(0.8)
        self.task.send_key(self.get_resonance_key())
        self.sleep(0.4)
        self.task.send_key(self.get_resonance_key())
        self.sleep(0.2)
        self.switch_next_char()