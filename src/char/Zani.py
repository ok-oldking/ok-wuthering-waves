import time

from src.char.BaseChar import BaseChar, Priority
from src.combat.CombatCheck import aim_color
from src.char.BaseChar import forte_white_color

class Zani(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.liberaction_time = 0
        self.in_liberation = False
        
    def reset_state(self):
        super().reset_state()
        self.liberaction_time = 0
        self.in_liberation = False
        
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.5)
        self.check_liber()
        if self.in_liberation and self.liberation_available() and self.liberation2_ready():   
            start = time.time()
            self.click_liberation()
            self.check_liber()
            if self.in_liberation:
                self.switch_next_char()
                if time.time() - start > 2:
                    self.add_freeze_duration(start, time.time()-start)
                    self.logger.debug(f'Zani click liber2 in {time.time()-start}')  
                    self.in_liberation = False
                return
            
        if not self.in_liberation and self.resonance_available() and self.resonance_light():
            self.resonance_until_not_light()
            self.continues_normal_attack(0.4)            
            return self.switch_next_char()
            
        if not self.in_liberation and self.liberation_available():
            if self.click_liberation():
                self.liberaction_time = time.time()
                self.continues_normal_attack(0.3)
        self.check_liber()                           
        if self.in_liberation:
            self.continues_normal_attack(0.8)
            if self.liberation_available() and self.liberation2_ready():   
                start = time.time()
                self.click_liberation()
                self.check_liber()
                if self.in_liberation:
                    self.switch_next_char()
                    if time.time() - start > 2:
                        self.add_freeze_duration(start, time.time()-start)
                        self.logger.debug(f'Zani click liber2 in {time.time()-start}')  
                        self.in_liberation = False
                    return
            return self.switch_next_char()    
        if self.resonance_available():
            self.resonance_until_not_light()
            self.continues_normal_attack(0.4)
            return self.switch_next_char()   
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()        
        self.continues_normal_attack(0.1)
        self.switch_next_char()          

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
# FIXME: 3c阵容菲比延奏有概率给到其他第三人
# FIXME: In a party with 3 attacker, Phoebe may switch to others while under intro.
        if self.in_liberation:
            if self.time_elapsed_accounting_for_freeze(self.liberaction_time) > 17:
                return Priority.MAX
            return 10000
        else:
            return super().do_get_switch_priority(current_char, has_intro)
            
    def liberation2_ready(self):
        if self.time_elapsed_accounting_for_freeze(self.liberaction_time) > 16:
            return True
# FIXME: 当能量空时尝试提早r2结束状态，但Forte图像为淡入，高概率出现误识别情况
# FIXME: An attempt is made to end the state of liberation earlier while energy empty.
#        However the forte image fading in result in a high probability of misidentification.

#        if self.time_elapsed_accounting_for_freeze(self.liberaction_time) > 12 and not self.is_forte_full():
#            return True
        return False
        
    def has_long_actionbar(self):
        if self.in_liberation:
            return True
        return False
        
    def resonance_until_not_light(self):
        start = time.time()
        while self.current_resonance() and not self.has_cd('resonance'):
            self.send_resonance_key()            
            if time.time() - start > 1:
                return
            self.check_combat()
            self.task.next_frame()
            
    def resonance_light(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3105, 1845, 3285, 2010, name='zani_resonance', hcenter=True)
        light_percent = self.task.calculate_color_percentage(zani_light_color, box)
        self.logger.info(f'Zani_resonance_light_percent {light_percent}')
        return light_percent > 0.005  
            
    def has_target(self,in_liber = False):
        if in_liber:
            outer_box = 'box_target_enemy_long'
            inner_box = 'box_target_enemy_long_inner'
        else:
            outer_box = 'box_target_enemy'
            inner_box = 'box_target_enemy_inner'
        aim_percent = self.task.calculate_color_percentage(aim_color, self.task.get_box_by_name(outer_box))
        aim_inner_percent = self.task.calculate_color_percentage(aim_color, self.task.get_box_by_name(inner_box))
        if aim_percent - aim_inner_percent > 0.02:
            return True
        return False
           
    def check_liber(self):
        if self.has_target(self.in_liberation):
            pass
        elif self.has_target(not self.in_liberation):
            self.in_liberation = not self.in_liberation
        self.check_combat()
        return self.in_liberation
        
    def is_forte_full(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 2251, 1993, 2311, 2016, name='forte_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        self.logger.info(f'forte_color_percent {white_percent}')
        return white_percent > 0.04   
        
zani_light_color = {
    'r': (245, 255),  # Red range
    'g': (245, 255),  # Green range
    'b': (205, 225)  # Blue range
}  