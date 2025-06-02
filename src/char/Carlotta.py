import time

from src.char.BaseChar import BaseChar, Priority


class Carlotta(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_echo = 0
        self.press_w = -1
        self.check_teammate = -1

    def reset_state(self):
        super().reset_state()
        self.last_echo = 0
        self.press_w = -1
        self.check_teammate = -1

    def do_perform(self):
        self.bullet = 0
        if self.press_w == -1:
            self.press_w = 0
            if self.task.name and self.task.name == "Farm 4C Echo in Dungeon/World":
               self.press_w = 1 
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.bullet = 1
            self.continues_normal_attack(1.2)
            if self.check_outro() in {'char_zhezhi','char_taoqi'}:
                self.do_perform_outro()
                return self.switch_next_char()
        if self.is_forte_full() and not self.waiting_outro():
            self.heavy_attack()
            return self.switch_next_char()
        if self.liberation_available() and not self.need_fast_perform() and not self.waiting_outro():
            if self.press_w == 1:
                self.task.send_key_down(key='w')
                while self.liberation_available():                
                    self.click_liberation()
                    self.task.send_key_up(key='w')
                    self.check_combat()
                    self.task.send_key_down(key='w')
                self.task.send_key_up(key='w')
            else:
                while self.liberation_available():                
                    self.click_liberation()
                    self.check_combat()
            self.click_echo()
            self.last_echo = time.time()
            return self.switch_next_char()
        if self.resonance_available():
            if self.bullet == 0:
                self.heavy_attack()
            if self.click_resonance()[0]:
                return self.switch_next_char()
        if self.echo_available():
            self.click_echo()
            return self.switch_next_char()
        self.continues_normal_attack(0.31)
        self.switch_next_char()       

    def do_perform_outro(self):
        clicked = True
        while clicked:
            clicked = False
            if self.is_forte_full():
                self.heavy_attack(1.5)
                clicked = True
            if self.liberation_available():
                if self.press_w == 1:
                    self.task.send_key_down(key='w')
                    while self.liberation_available():                
                        self.click_liberation()
                        self.task.send_key_up(key='w')
                        self.check_combat()
                        self.task.send_key_down(key='w')
                        self.task.send_key_up(key='w')
                else:
                    while self.liberation_available():                
                        self.click_liberation()
                        self.check_combat()
                clicked = True
            if self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                clicked = True
        if self.click_echo():
            self.last_echo = time.time()
            clicked = True
        self.continues_normal_attack(0.1)
        
    def waiting_outro(self):
        if self.check_teammate == -1:
            self.check_teammate = 0
            for i, char in enumerate(self.task.chars):
                self.logger.info(f'find char: {char}')
                if char.char_name in {'char_zhezhi','char_taoqi'}:
                    self.logger.info(f'find supporter: {char}')
                    self.buffer = char
                    self.check_teammate = 1
        if self.check_teammate == 1:
            self.logger.info(f'{self.buffer} has con {self.buffer.current_con}')
            if self.buffer == 'char_zhezhi' and self.buffer.current_con > 0.65:
                return True
            if self.buffer == 'char_taoqi' and self.buffer.current_con > 0.8:
                return True
        return False
          
    def has_long_actionbar(self):
        return True

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro and current_char.char_name in {'char_zhezhi','char_taoqi'}:
            return Priority.MAX
        if self.time_elapsed_accounting_for_freeze(self.last_echo, True) < 3:
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def click_liberation(self, con_less_than=-1, send_click=False, wait_if_cd_ready=0, timeout=5):
        if con_less_than > 0:
            if self.get_current_con() > con_less_than:
                return False
        self.logger.debug(f'click_liberation start')
        start = time.time()
        last_click = 0
        clicked = False
        while time.time() - start < wait_if_cd_ready and not self.liberation_available() and not self.has_cd(
                'liberation'):
            self.logger.debug(f'click_liberation wait ready {wait_if_cd_ready}')
            if send_click:
                self.click(interval=0.1)
            self.task.next_frame()
        while self.liberation_available():  # clicked and still in team wait for animation
            self.logger.debug(f'click_liberation liberation_available click')
            now = time.time()
            if now - last_click > 0.1:
                self.send_liberation_key()
                if not clicked:
                    clicked = True
                    self.update_liberation_cd()
                last_click = now
            if time.time() - start > timeout:
                self.task.raise_not_in_combat('too long clicking a liberation')
            # new
            if self.press_w == 1:
                self.task.send_key_up(key='w')
                self.check_combat()
                self.task.send_key_down(key='w')
            else:
                self.check_combat()
            self.task.next_frame()
        if clicked:
            if self.task.wait_until(lambda: not self.task.in_team()[0], time_out=0.4):
                self.task.in_liberation = True
                self.logger.debug(f'not in_team successfully casted liberation')
            else:
                self.task.in_liberation = False
                self.logger.error(f'clicked liberation but no effect')
                return False
        start = time.time()
        while not self.task.in_team()[0]:
            self.task.in_liberation = True
            if not clicked:
                clicked = True
                self.update_liberation_cd()
            if send_click:
                self.click(interval=0.1)
            if time.time() - start > 7:
                self.task.in_liberation = False
                self.task.raise_not_in_combat('too long a liberation, the boss was killed by the liberation')
            self.task.next_frame()
        duration = time.time() - start
        self.add_freeze_duration(start, duration)
        self.task.in_liberation = False
        if clicked:
            self.logger.info(f'click_liberation end {duration}')
        return clicked
