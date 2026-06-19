import time

from src.char.BaseChar import BaseChar

class Lucy(BaseChar):
    FORTE_TIMEOUT = 8.0  # 攒能量防卡死超时
    NORMAL_ATTACK_DURATION = 1.0
    HEAVY_ATTACK_TAP = 1.2
    LIB_HOLD_DURATION = 2.8
    LIB_CD_WAIT = 1.5

    def do_perform(self):
        if self.perform_standard():
            return self.switch_next_char()
        if self.perform_combat():
            return self.switch_next_char()

    def perform_standard(self):
        if self.is_forte_full():
            self.logger.info("Lucy forte already full, skip to combat.")
            return False

        start_time = time.time()
        while not self.is_forte_full():
            # 防卡死机制
            if time.time() - start_time > self.FORTE_TIMEOUT:
                self.logger.warning("Lucy failed to full forte, timeout reached.")
                return False  # 超时未满，返回 False 防止卡死，直接进入切人环节
                
            if self.resonance_available():
                self.click_resonance()
            self.heavy_attack(self.HEAVY_ATTACK_TAP)    
            if self.resonance_available():
                self.click_resonance()
            
            if self.is_forte_full():
                break
            self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
            self.f_break()

        return True
    
    def perform_combat(self):
        # 2次重击
        self.heavy_attack(self.HEAVY_ATTACK_TAP)
        self.continues_normal_attack(0.1)
        self.heavy_attack(self.HEAVY_ATTACK_TAP)
        self.f_break()
        if self.liberation_available():
            self.perform_liberation()

        return True

    def perform_liberation(self):
        self.click_liberation(send_click=True,wait_if_cd_ready=self.LIB_CD_WAIT)
        self.record_liberation_use()
        self.logger.info('Lucy perform lib')
        for _ in range(11):
            self.click()
        self.logger.info('Lucy perform lib end')
