from src.char.BaseChar import BaseChar


class HavocRover(BaseChar):
    def do_perform(self):
        self.click_liberation()
        if self.click_resonance()[0]:
            return self.switch_next_char()
        if self.is_forte_full():
            self.logger.info(f'forte_full, and liberation_available, heavy attack')
            self.wait_down()
            self.heavy_attack()
            self.sleep(0.4)
            if self.click_resonance()[0]:
                return self.switch_next_char()
        self.click_echo()
        self.switch_next_char()
