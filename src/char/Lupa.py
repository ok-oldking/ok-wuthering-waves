import time

from src.char.BaseChar import BaseChar, Priority


class Lupa(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.4)
        self.click_echo()
        if self.task.find_one('lupa_wolf_icon2', threshold=0.85):
            start = time.time()
            while time.time() - start < 1:
                self.send_resonance_key()
                if not self.task.find_one('lupa_wolf_icon2', threshold=0.85):
                    self.last_liberation = -1
                    break
                self.check_combat()
                self.task.next_frame() 
            return self.switch_next_char()
        if self.still_in_liberation():
            self.logger.debug('perform in liberation')
            self.click_jump_with_click(2)
            start = time.time()
            click = False           
            while time.time() - start < 2.2:
                self.click()
                if self.task.find_one('lupa_wolf_icon2', threshold=0.85):
                    click = True
                    break
                self.check_combat()
                self.task.next_frame() 
            if not click and self.is_forte_full():
                self.heavy_attack()
            return self.switch_next_char() 
        if not self.need_fast_perform() and self.click_liberation():
            self.continues_normal_attack(0.3)
            return self.switch_next_char() 
        if self.is_forte_full():
            if self.flying():
                self.task.wait_until(lambda: not self.is_forte_full(), post_action=self.click_with_interval, time_out=2)
            else:
                self.heavy_attack()
            return self.switch_next_char()
        if self.click_resonance()[0]:
            return self.switch_next_char()       
        self.continues_normal_attack(0.1)
        self.switch_next_char()
        
    def still_in_liberation(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation) < 12     

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.still_in_liberation():
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)
        
    def click_jump_with_click(self, delay=0.1):
        start = time.time()
        click = 0
        while True:
            if time.time() - start > delay:
                break
            if click == 0:
                self.task.send_key('SPACE')
            else:
                self.click()
            click = 1 - click
            self.check_combat()
            self.task.next_frame()