from src.char.BaseChar import BaseChar


class Camellya(BaseChar):

    def do_perform(self):
        self.click_liberation()
        if self.is_con_full():
            self.logger.info(f'confull')
            if self.click_resonance()[0]:
                self.sleep(0.2)
            if self.click_resonance()[0]:
                self.sleep(0.2)
            self.continues_normal_attack(4)
            self.click_resonance()
            return self.switch_next_char()
        if self.click_resonance()[0]:
            return self.switch_next_char()
        self.heavy_attack(1.2)
        self.switch_next_char()
