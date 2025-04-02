import time
from src.char.BaseChar import BaseChar, forte_white_color

class Cantarella(BaseChar):     
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_forte = 0
        
    def reset_state(self):
        super().reset_state()
        self.last_forte = 0
        
    def do_perform(self):
        heavy_ready = False
        self.logger.info(f'forte_cd {self.time_elapsed_accounting_for_freeze(self.last_forte)}')
        if self.has_intro:
            self.continues_normal_attack(1.2)
            heavy_ready = True
        if self.click_resonance()[0]:
            heavy_ready = True
        if self.click_liberation():
            heavy_ready = True
        if self.is_forte_full() and self.forte_ready() and heavy_ready:
            self.heavy_attack_combo()
            return self.switch_next_char()
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()
        self.continues_normal_attack(0.1)
        self.switch_next_char()
    
    def forte_ready(self):
        return self.time_elapsed_accounting_for_freeze(self.last_forte) > 18
        
    def heavy_attack_combo(self):
        start = time.time()
        forte_delay = start
        self.heavy_attack(1.2)
        click = 0
        while self.forte_ready():            
            if time.time() - start > 8:
                break
            if self.is_forte_full():
                forte_delay = time.time()
            elif time.time() - forte_delay > 0.5:
                break
            if click == 0:
                self.click()
            else:
                self.send_resonance_key()
            click = 1 - click
            self.check_combat()
            self.task.next_frame()
        self.last_forte = time.time()        

    def is_forte_full(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 2251, 1993, 2311, 2016, name='forte_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        self.logger.info(f'forte_color_percent {white_percent}')
        return white_percent > 0.03        

##########################            
    def resonance_havoc(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3105, 1845, 3285, 2010, name='cantarella_resonance', hcenter=True)
        havoc_percent = self.task.calculate_color_percentage(cantarella_havoc_color, box)
        self.logger.info(f'cantarella_havoc_color_percent {havoc_percent}')
        return havoc_percent > 0.01   
                
    def resonance_until_not_havoc(self):
        start = time.time()
        b = False
        while self.resonance_havoc() or time.time() - start < 0.5:
            self.task.send_resonance_key()
            b = True
            if time.time() - start > 2:
                return False
            self.check_combat()
            self.task.next_frame()
        return b
            
cantarella_havoc_color = {
    'r': (225, 255),  # Red range
    'g': (60, 90),  # Green range
    'b': (160, 190)  # Blue range
}  
