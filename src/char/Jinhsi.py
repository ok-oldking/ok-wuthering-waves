import time

from src.char.BaseChar import BaseChar, Priority


class Jinhsi(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_free_intro = 0  # free intro every 25 sec
        self.has_free_intro = False
        self.incarnation = 0
        self.last_fly_e_time = 0
        self.e2_last = 0

    def do_perform(self): 
        self.has_free_intro = False
        if self.has_intro: 
            if self.incarnation == 0:
                self.e2_last = time.time()
            self.sleep(0.8)
        self.click_echo()
        if self.incarnation == 2:
            self.handle_incarnation()
            return self.switch_next_char(free_intro=self.has_free_intro) 
        if (self.time_elapsed_accounting_for_freeze(self.e2_last) < 4.5 and self.incarnation == 0) or self.resonance_light() or self.incarnation == 1:
            self.handle_intro()
            return self.switch_next_char(free_intro=self.has_free_intro)            
        if self.check_team_con() and not self.need_fast_perform() and self.resonance_available() and self.time_elapsed_accounting_for_freeze(self.last_fly_e_time) > 12:
            if self.attack_until_resonance():
                self.e2_last = time.time()
                self.handle_intro() 
                return self.switch_next_char(free_intro=self.has_free_intro)
        self.continues_normal_attack(0.1)
        self.switch_next_char(free_intro=self.has_free_intro)

    def reset_state(self):
        super().reset_state()
        self.incarnation = 0
        self.has_free_intro = False
        self.e2_last = 0
        self.last_fly_e_time = 0
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro or self.incarnation > 0 or self.time_elapsed_accounting_for_freeze(self.e2_last) < 4.5:
            self.logger.info(
                f'switch priority max because has_intro {has_intro} incarnation {self.incarnation} e2_cd {self.e2_last}')
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro)
    
    def count_resonance_priority(self):
        if self.time_elapsed_accounting_for_freeze(self.last_fly_e_time) > 12:
            return 10
        return 0

    def count_liberation_priority(self):
        return 0
        
    def handle_incarnation(self):
        self.incarnation = 0
        self.logger.info('handle_incarnation click_resonance start')
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(self.last_fly_e_time) < 10.5: 
            self.click(interval=0.1)
            if time.time() - start > 8:
                return
            if self.resonance_light():
                self.e2_last = time.time()
                result = self.resonance_until_not_light()
                if result == 1:
                    self.last_fly_e_time = time.time()
                    self.incarnation = 1
                if result > 0:
                    return 
            self.check_combat()
            self.task.next_frame()                    

    def handle_intro(self):
        self.logger.info('handle_intro start')
        start = time.time()
        if self.has_cd('resonance') and self.time_elapsed_accounting_for_freeze(self.last_fly_e_time) < 12:
            self.logger.info('e2 has cd')
            return
        if self.incarnation == 0:
            if self.resonance_until_not_light() == 1:            
                self.last_fly_e_time = time.time()
                if not self.click_liberation():
                    self.dodge()
                self.continues_normal_attack(0.1)
                self.incarnation = 1
                if self.check_outro() in {'char_zhezhi','char_taoqi','char_cantarella','char_brant'}:
                    self.incarnation = 2
                    self.handle_incarnation()
                    return
        if self.incarnation == 1:
            if self.check_outro() in {'char_zhezhi','char_taoqi','char_cantarella','char_brant'}:
                self.incarnation = 2
                self.handle_incarnation()
                return
            while self.time_elapsed_accounting_for_freeze(self.last_fly_e_time) < 11:
                if self.resonance_available():
                    self.click_resonance()
                    self.incarnation = 2                    
                    self.check_animation()
                    return
                self.task.click(interval=0.1)
                self.check_combat()
                self.task.next_frame()
        self.incarnation = 0 

                 
    def dodge(self, duration=0.1):
        self.check_combat()
        self.task.send_key_down(key='w')
        self.task.mouse_down(key='right')
        self.sleep(duration)
        self.task.mouse_up(key='right')
        self.task.send_key_up(key='w')
    
    def resonance_light(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3105, 1845, 3285, 2010, name='jinhsi_resonance', hcenter=False)
        yellow_percent = self.task.calculate_color_percentage(jinhsi_yellow_color, box)
        return yellow_percent > 0.03   

    def attack_until_resonance(self):
        start = time.time()
        last = start
        while time.time() - start < 7:           
            self.click(interval=0.1)
            if self.resonance_light():
                if time.time()-last > 0.1:
                    return True
            else:
                last = time.time()
            self.task.next_frame()
            self.check_combat()
        return False

        
    def check_team_con(self):
        for i, char in enumerate(self.task.chars):
            self.logger.debug(f'find char: {char}')
            if char == self or char.current_con < 0.8:
                continue
            return False
        return True
                
        
    def resonance_until_not_light(self):
        start = time.time()
        b = 0
        while not self.resonance_light() or not self.resonance_available():
            if time.time() - start > 1:
                break
            self.check_combat()
            self.task.next_frame()
        while self.resonance_available() and self.resonance_light():
            self.send_resonance_key() 
            b = 1
            if time.time() - start > 2:
                return 0
            if self.check_animation():
                return 2
            self.check_combat()
            self.task.next_frame() 
        if self.check_animation():
            return 2
        return b

    def check_animation(self):
        if self.task.in_team()[0]:
            return False
        animation_start = 0
        self.task.in_liberation = True
        while not self.task.in_team()[0]:
            if animation_start == 0:
                self.logger.info('Jinhsi handle_incarnation start animation')
                animation_start = time.time()
            self.check_combat()
            self.task.next_frame()
        self.task.in_liberation = False
        if animation_start == 0:
            return False
        self.add_freeze_duration(animation_start) 
        self.incarnation = 0
        self.e2_last = 0
        if self.time_elapsed_accounting_for_freeze(self.last_free_intro) > 25:
            self.has_free_intro = True
            self.last_free_intro = time.time()
        return True
            
jinhsi_yellow_color = {
    'r': (235, 255),  # Red range
    'g': (235, 255),  # Green range
    'b': (200, 230)  # Blue range
}  