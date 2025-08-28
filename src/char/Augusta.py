import time
import re

from ok import find_boxes_by_name
from src.char.BaseChar import BaseChar
from src.task.BaseWWTask import binarize_for_matching
from src import text_white_color

class Augusta(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.13)
        if self.flying():
            self.wait_down() 
        start = time.time()
        timeout = lambda: time.time() - start < 8
        while timeout():            
        #    if self.check_ascendancy():
        #        self.logger.debug('Augusta performs ascendancy') 
        #        self.task.wait_until(lambda: not self.check_ascendancy(), post_action=self.send_resonance_key, time_out=3)
        #        if not self.check_majesty():
        #            self.wait_down()   
            if self.check_majesty() :
                self.logger.debug('Augusta performs majesty')
                if self.perform_majesty():
                    self.send_echo_key()
                    return self.switch_next_char()
            if self.flying():
                self.shorekeeper_auto_dodge()
            if self.check_prowess() and self.perform_prowess():                
                if time.time() - start > 3:
                    return self.switch_next_char()
            if self.resonance_available():
                self.logger.debug('Augusta performs single resonance') 
                now = time.time()
                self.click_resonance()
                self.logger.debug(f'time = {time.time() - now}') 
                if time.time() - now < 1:
                    if self.flying():
                        continue
                    self.update_res_cd()
                    if self.task.wait_until(self.check_prowess, time_out=1) and self.perform_prowess():
                        if time.time() - start > 3 and not self.flying():
                            return self.switch_next_char()
                else: 
                    if self.check_majesty() and self.perform_majesty(wait_down=True):
                        self.send_echo_key()
                    return self.switch_next_char()
            if self.liberation_available():
                self.logger.debug('Augusta performs single liberation')
                self.task.wait_until(lambda: not self.liberation_available, post_action=self.send_liberation_key, time_out=1)
                self.update_liberation_cd()
                if time.time() - start > 3:
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
        self.sleep(0.1)
        self.continues_right_click(0.05)
        self.continues_normal_attack(0.45)
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
    #    texts = self.task.ocr(box=self.task.box_of_screen(0.58, 0.91, 0.61, 0.93, hcenter=True),
    #                     target_height=540, name="augusta_ascendancy")
    #    fps_text = find_boxes_by_name(texts,'e')
    #    if fps_text:
    #        return True
    
    def liberation_available(self):
        current = self.task.calculate_color_percentage(text_white_color,
                                                  self.task.get_box_by_name('box_liberation'))
        return current > 0 and bool(self.task.find_one('Augusta_lib1', threshold=0.6))
            
    def check_majesty(self):
        current = self.task.calculate_color_percentage(text_white_color,
                                                  self.task.get_box_by_name('box_liberation'))
        return current > 0 and bool(self.task.find_one('Augusta_lib2', threshold=0.6))
        
    def check_prowess(self):
        long_inner_box = 'box_target_enemy_long_inner'
        if self.task.find_one(long_inner_box, box=self.task.get_box_by_name(long_inner_box), threshold=0.85):
            return True
            
    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)   
                
    def count_echo_priority(self):
        return 0
