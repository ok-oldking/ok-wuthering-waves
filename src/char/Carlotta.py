import time

from src.char.BaseChar import BaseChar, Priority


class Carlotta(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_echo = 0

    def reset_state(self):
        super().reset_state()
        self.last_echo = 0

    def do_perform(self):
        self.bullet = 0
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.bullet = 1
            self.continues_normal_attack(1.2)
        if self.is_forte_full():
            self.heavy_attack()
            return self.switch_next_char()
        if not self.need_fast_perform() and self.liberation_available():
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

    def has_long_actionbar(self):
        return True

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
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
