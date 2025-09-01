import time
import re

from ok import find_boxes_by_name
from src.char.BaseChar import BaseChar
from src.task.BaseWWTask import binarize_for_matching
from src import text_white_color

""" 
    几个长派生帧动作的切人时间阈值,改小可以减少站场时间
    初始为 3
"""
switch_time = 3

class Augusta(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.13)
        if self.flying():
            self.wait_down() 
        start = time.time()
        timeout = lambda: time.time() - start < 6
        while timeout():              
            if self.check_majesty() :
                self.logger.debug('Augusta performs majesty')
                if self.perform_majesty():
                    self.send_echo_key()
                    return self.switch_next_char()
            if self.flying():
                self.shorekeeper_auto_dodge()
            if self.check_prowess() and self.perform_prowess():                
                if time.time() - start > switch_time:
                    return self.switch_next_char()
            if self.resonance_available():
                self.logger.debug('Augusta performs single resonance') 
                now = time.time()
                self.click_resonance()
                self.logger.debug(f'time = {time.time() - now}') 
                if time.time() - now < 1.4:
                    if self.flying():
                        continue
                    if self.task.wait_until(self.check_prowess, time_out=1) and self.perform_prowess():
                        if time.time() - start > switch_time and not self.flying():
                            return self.switch_next_char()
                else: 
                    if self.check_majesty():
                        self.wait_down()
                        if self.perform_majesty():
                            self.send_echo_key()
                    return self.switch_next_char()
            if self.liberation_available():
                self.logger.debug('Augusta performs single liberation')
                if self.task.wait_until(lambda: not self.liberation_available(), post_action=self.send_liberation_key, time_out=2):
                    self.update_liberation_cd()
                    return self.switch_next_char()     
            self.click()
            self.check_combat()
            self.task.next_frame()  
        self.send_echo_key()
        self.switch_next_char()  
        
    def perform_prowess(self):
        self.logger.debug('Augusta performs prowess') 
        if not self.heavy_click_forte(self.check_prowess):
            return False
        self.continues_normal_attack(0.3)
        return True
    
    def perform_majesty(self, time_out=0.6, wait_down = False):        
        self.task.send_key_down(self.get_liberation_key())
        self.task.in_liberation = True
        if wait_down:
            time_out = 0.2
            self.task.wait_until(lambda: not self.task.in_team()[0] or not self.flying(), time_out=2)
        self.task.wait_until(lambda: not self.task.in_team()[0], time_out=time_out)
        start = time.time()
        self.task.send_key_up(self.get_liberation_key())
        if self.task.in_team()[0]:
            self.logger.debug('Augusta performs majesty failed: not in animation')
            self.task.in_liberation = False
            return False
        self.task.wait_until(lambda: self.task.in_team()[0], post_action=self.click, time_out=10)
        self.add_freeze_duration(start, time.time()-start)         
        self.logger.info(f'click_liberation end {time.time()-start}')
        
        return True
            
    def check_ascendancy(self):
        return False
    
    def liberation_available(self):
        return self.current_liberation() > 0 and bool(self.task.find_one('Augusta_lib1', threshold=0.6))
            
    def check_majesty(self):
        return self.current_liberation() > 0 and bool(self.task.find_one('Augusta_lib2', threshold=0.6))
     
    def check_prowess(self):
        long_inner_box = 'box_target_enemy_long_inner'
        if self.task.find_one(long_inner_box, box=self.task.get_box_by_name(long_inner_box), threshold=0.85):
            return True
    
    def resonance_available(self):
        return not self.has_cd('resonance')
        
    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)   
                
    def count_echo_priority(self):
        return 0

    def on_combat_end(self, chars):
        next_char = str((self.index + 1) % len(chars) + 1)
        self.logger.debug(f'Cantarella on_combat_end {self.index} switch next char: {next_char}')
        self.task.send_key(next_char)
 