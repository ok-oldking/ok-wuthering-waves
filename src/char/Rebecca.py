import time
from src.char.BaseChar import BaseChar

class Rebecca(BaseChar):
    FORTE_TIMEOUT = 5.5          # 防卡死超时
    NORMAL_ATTACK_DURATION = 0.5
    HEAVY_ATTACK_DURATION = 1.5
    LIB_HOLD_DURATION = 5.2
    LIB_CD_WAIT = 1.5
    DODGE_INTERVAL = 4.0         # 闪避最小间隔（秒）

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 用 None 作为哨兵，确保首次登场必然触发蓄力逻辑
        self._forte_built_at = None

    def do_perform(self):
        if self.perform_combat():
            return self.switch_next_char()

    def perform_combat(self):
        """
        核心战斗逻辑状态机
        """
        # 状态分支 1：大招就绪，但核心能量未满 -> 触发前置攒能序列
        if self.liberation_available() and not self.is_forte_full():
            self._build_forte_sequence()
        
        # 状态分支 2：大招就绪（可能由分支 1 攒满能量后下摆至此，或开局即就绪）
        if self.liberation_available():
            self.perform_enhanced_heavy()
            self.perform_liberation()
            self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
            return True
        
        # 状态分支 3：常规循环（大招未就绪）
        self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
        self.click_resonance()
        return True

    def _build_forte_sequence(self):
        """
        前置攒能与切人防重入保护机制
        """
        self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
        self.continues_right_click(duration=0.1, interval=0.1, direction_key='s')
        last_dodge = time.time()
        self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
        self.click_resonance()
        
        switch_in = getattr(self, 'last_switch_in_time', -1)
        
        # 幂等性校验：防止切人失败时轮询导致的重复蓄力
        if self._forte_built_at != switch_in:
            start_time = time.time()
            while time.time() - start_time < self.FORTE_TIMEOUT:
                if self.is_forte_full():
                    break
                
                now = time.time()
                if now - last_dodge >= self.DODGE_INTERVAL:
                    self.continues_right_click(duration=0.1, interval=0.1, direction_key='s')
                    last_dodge = now
                
                self.heavy_attack(self.HEAVY_ATTACK_DURATION)
                
                if hasattr(self, 'task') and hasattr(self.task, 'next_frame'):
                    self.task.next_frame()
            else:
                self.logger.warning("Rebecca full forte timeout reached.")
            
            self._forte_built_at = switch_in
        
        self.perform_enhanced_heavy()

    def perform_liberation(self):
        if self.echo_available():
            self.click_echo(time_out=0)
        if self.has_long_action2() and self.liberation_available():
            self.click_liberation(wait_if_cd_ready=self.LIB_CD_WAIT)
            self.perform_hmg_mode()
            
    def perform_enhanced_heavy(self):
        if self.is_mouse_forte_full():
            self.heavy_attack(0.5)

    def perform_hmg_mode(self):
        start = time.time()
        last_liberation = start
        while self.time_elapsed_accounting_for_freeze(start) < self.LIB_HOLD_DURATION:
            self.click(interval=0.08)
            now = time.time()
            if now - last_liberation > 0.9:
                self.send_liberation_key()
                last_liberation = now
            self.check_combat()
            self.task.next_frame()