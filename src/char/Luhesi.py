import time

from src.char.BaseChar import BaseChar, Priority


class Luhesi(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if self.luhesi_lib_available() and self.click_liberation(wait_if_cd_ready=0):
            self.f_break()
            return True

    def luhesi_lib_available(self):
        return self.available('luhesi_lib', check_cd=False) and not self.has_cd('liberation')

    def perform_everything(self):
        start = time.time()
        last_click = 'resonance'
        while self.time_elapsed_accounting_for_freeze(start) < 8:
            self.check_combat()
            if self.handle_heavy():
                if self.luhesi_lib_available():
                    continue
                else:
                    return
            elif self.lib():
                start = time.time()
            elif last_click == 'resonance':
                self.click(after_sleep=0.1)
                last_click = 'click'
            else:
                self.send_resonance_key(post_sleep=0.1)
                last_click = 'resonance'
            self.sleep(0.01)

    def handle_heavy(self):
        start = time.time()
        have_kick = False
        while self.task.find_one('luhesi_kick', threshold=0.7) and time.time() - start < 3:
            have_kick = True
            self.click(after_sleep=0.1)
        return have_kick
