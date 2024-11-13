from src.char.BaseChar import BaseChar


class Chixia(BaseChar):
    def do_perform(self):
        #more of a sub dps build
        if self.has_intro:
            self.continues_normal_attack(1.5)
        self.click_liberation()
        self.click_echo_and_swapout(only_if_echo_has_animation=True)
        res_key = self.get_resonance_key()
        if self.is_forte_full(): # this is broken on chixia it returns false positives 
            if self.resonance_available():
                self.task.send_key(res_key,down_time=3.02)# how do i walk forward here ?
                self.normal_attack()
                self.sleep(0.6)
                return self.switch_next_char()
        self.task.send_key(res_key,down_time=0)
        self.switch_next_char()
    # def do_perform(self):
    #     if self.resonance_available():
    #         if self.bullets > 35:
    #             self.task.send_key_down(self.get_resonance_key())
    #             self.sleep(3)
    #             self.click
    #         else:
    #             self.task.send_key_up(self.get_resonance_key())
    #     self.switch_next_char()
