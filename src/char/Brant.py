import time
from src.char.BaseChar import BaseChar, Priority

class Brant(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.liberaction_time = 0
        self.in_liberaction = 0
        self.perform_anchor = 0
        
    def reset_state(self):
        super().reset_state()
        self.liberaction_time = 0
        self.perform_anchor = 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        if self.is_forte_full() and self.resonance_available():
            self.resonance_forte_full()
            self.in_liberaction = 0
            self.perform_anchor = time.time()
            return self.switch_next_char()
        if self.click_liberation():
            self.liberaction_time = time.time()
            self.in_liberaction = 1 
            self.continues_normal_attack(0.8)
        if self.still_in_liberation():
            self.click_jump_with_click(1.3)
            if self.is_forte_full() and self.resonance_available():
                self.resonance_forte_full()
                self.perform_anchor = time.time()
                self.in_liberaction = 0
            return self.switch_next_char()    
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()  
        self.click_jump_with_click(1.3)
        self.switch_next_char()
        
    def still_in_liberation(self):
        return self.time_elapsed_accounting_for_freeze(self.liberaction_time) < 12 and self.in_liberaction == 1
        
    def resonance_forte_full(self):
        start = time.time()        
        while self.resonance_available() and self.is_forte_full():
            self.send_resonance_key()
            if time.time() - start > 1 :
                break
            self.check_combat()
            self.task.next_frame()
            
    def click_jump_with_click(self, delay=0.1):
        start = time.time()
        click = 1
        while True:
            if time.time() - start > delay:
                break
            if click == 0:
                self.task.send_key('SPACE')
            else:
                self.click()
            click = 1 - click
            self.task.next_frame()
            
    def count_resonance_priority(self):
        return 0
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.perform_anchor) < 4:
            return Priority.MIN
        elif self.still_in_liberation():
            return 1000
        else:
            return super().do_get_switch_priority(current_char, has_intro)
