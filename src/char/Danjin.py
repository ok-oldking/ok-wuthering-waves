from src.char.BaseChar import BaseChar, WWRole

class Danjin(BaseChar):
    def count_resonance_priority(self):
        return 0
    def count_forte_priority(self):
        return 1
    def do_perform(self):
        res_key = self.get_resonance_key()
        if self.has_intro:
            for _ in range(12):
                self.task.send_key(res_key)
                self.sleep(0.1)
        self.danjin_heavy_hitters()
        i = 20 if self.role == WWRole.MainDps else 12
        for _ in range(i):
            self.task.click(interval=0.1)
            self.task.send_key(res_key)
            self.danjin_heavy_hitters()# this might lag abit ?
            self.sleep(0.1)
        self.switch_next_char()
    def danjin_heavy_hitters(self):
        if self.is_forte_full():
                self.heavy_attack()
                self.sleep(0.3)
                self.normal_attack()
        self.click_liberation()
        self.click_echo_and_swapout()
        