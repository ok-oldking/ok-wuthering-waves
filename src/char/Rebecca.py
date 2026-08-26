import time
from src.char.BaseChar import BaseChar

class Rebecca(BaseChar):
    LIB_HOLD_DURATION = 5.2
    LIB_ENTER_DURATION = 0.8

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_f_on_switch = False  # Rebecca 切人时不自动F，第一时间切 Lucy

    def do_perform(self):
        if self.perform_combat():
            return self.switch_next_char()

    def perform_combat(self):
        self._build_forte_sequence()
        return True

    def _build_forte_sequence(self):

        if self.has_intro:
            self.continues_normal_attack(1.3)
        else:
            self.continues_normal_attack(1.8)

        if self.has_intro:
            self.task.wait_until(lambda: self.resonance_available(), 2)
            self.click_resonance(post_sleep=1.5)
            self.click_resonance(post_sleep=1.5)
        else:
            self.task.wait_until(lambda: self.resonance_available(), 2)
            self.click_resonance(post_sleep=1.5)
            self.click_resonance(post_sleep=1.5)
            self.click_resonance(post_sleep=1)

        self.send_resonance_key()
        wait_start = time.time()
        while not self.is_mouse_forte_full() and time.time() - wait_start < 4.0:
            self.task.click()
            self.sleep(0.1)
            if hasattr(self.task, 'next_frame'):
                try:
                    self.task.next_frame()
                except Exception:
                    pass
        self.perform_enhanced_heavy()
        # 固定延迟再 Q
        self.sleep(1.3, check_combat=False)
        self.click_echo()
        self.perform_hmg_mode()

    def perform_enhanced_heavy(self):
        """强化重击执行逻辑：光环亮才短按重击"""
        if self.is_mouse_forte_full():
            self.heavy_attack(0.5)

    def perform_hmg_mode(self):
        enter_start = time.time()
        while time.time() - enter_start < self.LIB_ENTER_DURATION:
            self.send_liberation_key()
            self.sleep(0.1, check_combat=False)
        self.record_liberation_use()
        start = time.time()
        last_liberation = time.time()
        while time.time() - start < self.LIB_HOLD_DURATION:
            self.click(interval=0.08)
            now = time.time()
            if now - last_liberation > 0.9:
                self.send_liberation_key()
                last_liberation = now
            self.sleep(0.01, check_combat=False)
