import time
from src.char.BaseChar import BaseChar


class Rebecca(BaseChar):
    LIB_HOLD_DURATION = 5.2
    LIB_ENTER_DURATION = 0.8
    # 大招结束后的短时间内再次入场时，技能均在冷却，无可执行的完整连招，
    # 只做基础攻击并快速换人，避免空转耽误主C输出
    LIB_REENTER_WINDOW = 17.0
    NORMAL_ATTACK_DURATION = 0.5
    ATTACK_DURATION = 1.0
    ATTACK_TIMEOUT = 2.2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_f_on_switch = False  # 切入时不自动处决，交由队友处理
        self._last_liberation_at = -999.0  # 初始值：首次入场不受窗口限制

    def _in_reenter_window(self):
        return time.time() - self._last_liberation_at < self.LIB_REENTER_WINDOW

    def do_perform(self):
        if self.perform_combat():
            # 窗口内：普攻攒协奏（最多 2.2s）后换出
            if self._in_reenter_window():
                start = time.time()
                while not self.is_con_full() and time.time() - start < self.ATTACK_TIMEOUT:
                    self.continues_normal_attack(self.ATTACK_DURATION)
                    time.sleep(0.1)
            return self.switch_next_char()

    def perform_combat(self):
        # 窗口内再次入场：没有有效连招，快速让位
        if self._in_reenter_window():
            self.click_resonance()
            self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
            return True
        # 标准连招：不依赖大招/协奏状态，固定执行
        self._build_forte_sequence()
        return True

    def _build_forte_sequence(self):
        """变奏入场 2 次 E / 非变奏 3 次 E -> 末次 E 后普攻攒能量 -> 蓄力重击 -> 声骸 + 大招"""
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

        # 末次 E 后能量未满：普攻攒能直到蓄力图标出现（最多 4s）
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
        # 图标亮后蓄力重击（长按 1.5s）
        if self.is_mouse_forte_full():
            self.heavy_attack(1.5)
        # 声骸 + 大招
        self.click_echo()
        self.perform_hmg_mode()

    def perform_enhanced_heavy(self):
        """蓄力图标亮起时执行强化重击"""
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
        # 大招完成，启动快速让位窗口
        self._last_liberation_at = time.time()
