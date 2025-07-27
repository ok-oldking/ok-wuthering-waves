import time
from src.char.BaseChar import BaseChar, forte_white_color, Priority


class Cantarella(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = -1

    def do_perform(self):
        perform_under_outro = False
        if self.has_intro:
            self.continues_normal_attack(1.2)
            if self.check_outro() in {'char_roccia', 'char_sanhua', 'char_sanhua2'}:
                perform_under_outro = True
        self.click_liberation()
        if self.is_mouse_forte_full() or not self.is_forte_full():
            self.click_resonance()
            if perform_under_outro and self.flying():
                self.wait_down()
            if not self.flying() and self.is_mouse_forte_full():
                if self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
                    self.last_heavy = time.time()
            elif self.click_echo():
                return self.switch_next_char()
            else:
                self.continues_normal_attack(0.1)
                return self.switch_next_char()             
        forte_delay = time.time()
        count = -0.1
        while self.time_elapsed_accounting_for_freeze(self.last_heavy) < 8 and not self.is_mouse_forte_full():
            now = time.time()
            if self.resonance_available and self.click_resonance(send_click=False):
                if not perform_under_outro:
                    self.task.mouse_up()
                    return self.switch_next_char() 
            if not perform_under_outro and self.need_fast_perform() and self.time_elapsed_accounting_for_freeze(self.last_perform) > 1.1:
                break 
            if now - forte_delay > count:
                self.task.mouse_up()
                self.sleep(0.2)
                self.task.mouse_down()
                count += 1
            if self.is_forte_full():
                forte_delay = now
            elif now - forte_delay > 0.5:
                break
            self.check_combat()
            self.task.next_frame()
        self.task.mouse_up()
        self.click_echo()
        self.switch_next_char()
            
    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        if not self.is_mouse_forte_full() and self.is_forte_full():
            return not self.has_cd('resonance')
        return super().resonance_available()
        
    def on_combat_end(self, chars):
        next_char = str((self.index + 1) % len(chars) + 1)
        self.logger.debug(f'Camellya on_combat_end {self.index} switch next char: {next_char}')
        self.task.send_key(next_char)

    def is_forte_full(self):
        box = self.task.box_of_screen_scaled(5120, 2880, 3034, 2640, 3090, 2700, name='forte_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        self.logger.debug(f'forte_color_percent {white_percent}')
        return white_percent > 0.06
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro and current_char.char_name in {'char_roccia', 'char_sanhua', 'char_sanhua2'}:
            return Priority.MAX-1
        return super().do_get_switch_priority(current_char, has_intro)

