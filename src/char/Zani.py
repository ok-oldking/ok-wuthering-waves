import time

from src.char.BaseChar import BaseChar, Priority
from src.combat.CombatCheck import aim_color
from src.char.BaseChar import forte_white_color

class Zani(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.liberaction_time = 0
        self.in_liberation = False
        self.have_forte = False
        self.last_attack = 0
        self.final_attack = False
        
    def reset_state(self):
        self.last_attack = 0
        super().reset_state()
        
    def do_perform(self): 
        shield_attack = False
        if self.has_intro:
            self.continues_normal_attack(1.5)
        elif self.in_liberation:
            shield_attack = self.time_elapsed_accounting_for_freeze(self.last_attack) > 3
        self.check_liber()
        self.click_echo() 
        if self.in_liberation and self.liberation2_ready():          
            start = time.time()
            self.click_liberation()
            self.check_liber()
            if self.in_liberation:
                self.switch_next_char()
                if time.time() - start > 2:
                    self.add_freeze_duration(start, time.time()-start)
                    self.logger.info(f'Zani click liber2 in {time.time()-start}')  
                    self.in_liberation = False
                return
        if not self.in_liberation and self.resonance_available(): 
            if not self.resonance_until_not_light():
                self.logger.info('res+liber combo failed')
            self.continues_normal_attack(0.55)
        if not self.in_liberation and self.liberation_available():
            if self.click_liberation():
                self.in_liberation = True
                self.have_forte = True
                self.liberaction_time = time.time()
                self.last_attack = self.liberaction_time
                self.continues_normal_attack(1.1)
                self.logger.info('Zani click liber1.')   
                return self.switch_next_char()
        if self.in_liberation:
            self.last_attack = time.time()
    #开大时，zani离场再登场的平a，会打出普通攻击而不是强化攻击
    #算是bug，目前先延迟0.3秒，等kl修
            if shield_attack and not (self.final_attack or self.attack_light()):
                self.continues_normal_attack(0.3)
            self.continues_normal_attack(0.6)
            return self.switch_next_char()              
        self.continues_normal_attack(0.1)
        self.switch_next_char()          

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.in_liberation:
            return 10000
        else:
            return super().do_get_switch_priority(current_char, has_intro)
            
    def liberation2_ready(self):
        if not self.liberation_available(): 
            return False
        if (self.have_forte and self.final_attack) or self.attack_light():
            return False
        if self.time_elapsed_accounting_for_freeze(self.liberaction_time) > 18.3:
            return True
        if not self.have_forte and self.time_elapsed_accounting_for_freeze(self.liberaction_time) > 12:
            return True
        return False
        
    def has_long_actionbar(self):
        if self.check_liber():
            return True
        return False
        
    def resonance_until_not_light(self):
        start = time.time()
        b = False
        while self.current_resonance() and not self.has_cd('resonance'):
            self.send_resonance_key()            
            b = True
            if time.time() - start > 1:
                return False
            self.check_combat()
            self.task.next_frame()
        return b
            
    def attack_light(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 2690, 1845, 2860, 2010, name='zani_attack', hcenter=False)
        light_percent = self.task.calculate_color_percentage(zani_light_color, box)
        return light_percent > 0.01        
        
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
        else:
            self.in_liberation = not self.in_liberation
        return self.in_liberation        
           
    def switch_next_char(self, *args):
        self.have_forte = self.is_forte_full()
        if self.in_liberation:
            if self.attack_light():
                self.final_attack = False
            else:
                self.final_attack = not self.final_attack
        else:
            self.final_attack = False
        return super().switch_next_char(*args)
        
zani_light_color = {
    'r': (245, 255),  # Red range
    'g': (245, 255),  # Green range
    'b': (205, 225)  # Blue range
}