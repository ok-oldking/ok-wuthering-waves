import time

from src.char.BaseChar import BaseChar


class Roccia(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plunge_count = 0
        self.last_e = 0
        self.last_intro = 0
        self.can_plunge = False

    def do_perform(self):
        if self.has_intro:
            self.heavy_attack(1.6)
            self.sleep(0.1)
            self.last_intro = time.time()
            self.plunge()
            if not self.liberation_available() and not self.resonance_available():
                return self.switch_next_char()
        liberated = self.click_liberation()
        if self.click_resonance()[0] or not liberated:
            self.plunge()
            return self.switch_next_char()
        self.click_echo()
        return self.switch_next_char()

    def switch_next_char(self, post_action=None, free_intro=False, target_low_con=False):
        super().switch_next_char(post_action=self.update_tool_box, free_intro=free_intro,
                                 target_low_con=target_low_con)

    def update_tool_box(self, next_char, has_intro):
        if has_intro:
            next_char.has_tool_box = True

    def plunge(self):
        if self.need_fast_perform():
            self.normal_attack_until_can_switch()
            return
        start = time.time()
        self.task.send_key_down('w')
        while self.is_mouse_forte_full() and time.time() - start < 6:
            if time.time() - start > 2 and not self.has_cd('resonance') and not self.has_cd('liberation'):
                if self.click_liberation():
                    self.click_resonance()
                    start = time.time()
                    continue
            self.click(interval=0.1)
        self.task.send_key_up('w')
        return True
