from src.char.BaseChar import BaseChar


class Verina(BaseChar):

    def __init__(self, task, index, res_cd=20, echo_cd=20):
        super().__init__(task, index, res_cd, echo_cd)
        self.count_resonance = 0

    def do_perform(self):
        self.click_liberation()
        if self.is_forte_full():
            self.click_jump()
            self.normal_attack()
            while self.count_resonance > 0:
                self.logger.debug(f'The cumulative number of resonance skill releases is {self.count_resonance}')
                self.normal_attack()
                self.count_resonance -= 1
                self.sleep(0.2)
                self.logger.debug(f'attack...')
            
        if self.flying():
            self.normal_attack()
            return self.switch_next_char()
        if self.click_resonance(send_click=False)[0]:
            self.count_resonance += 1
            self.logger.debug(f'resonance skill releases,  count: {self.count_resonance}')
            return self.switch_next_char()
        self.click_echo()
        # if self.is_forte_full():
        #     self.heavy_attack()
        # self.normal_attack()
        self.switch_next_char()

    def count_base_priority(self):
        return - 1
