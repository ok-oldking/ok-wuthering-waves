import time
from src.char.BaseChar import BaseChar

class Lucy(BaseChar):
    FORTE_TIMEOUT = 6.2
    LIB_CD_WAIT = 1.5
    NORMAL_ATTACK_DURATION = 0.1
    HEAVY_ATTACK_DURATION = 0.8
    CLICK_INTERVAL = 0.1
    ENHANCED_HEAVY_INTERVAL = 0.5
    LIB_CLICK_COUNT = 11 #包含冗余点击

    def do_perform(self):
        if not self.is_forte_full():
            self.perform_standard()
            
        if self.is_forte_full():
            self.perform_combat()
            
        if self.perform_liberation():
            return self.switch_next_char()

    def perform_standard(self):
        """标准攒能量流程"""
        if self.is_forte_full():
            self.logger.info("Lucy forte is already full, skip standard build-up.")
            return False

        start_time = time.time()
        while not self.is_forte_full():
            # 防卡死超时机制
            if time.time() - start_time > self.FORTE_TIMEOUT:
                self.logger.warning("Lucy failed to fill forte, timeout reached.")
                break
                
            if self.resonance_available():
                self.click_resonance()
                
            self.heavy_attack(self.HEAVY_ATTACK_DURATION)  
            
            if self.resonance_available():
                self.click_resonance()

        self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
        return True

    def perform_combat(self):
        """满能量倾泻输出流程"""
        if not self.is_forte_full():
            self.logger.info("Lucy forte not full, skip combat.")
            return False
            
        self.f_break()
        if self.echo_available():
            self.click_echo(time_out=0)
            
        self.perform_enhanced_heavy()
        self.continues_normal_attack(self.NORMAL_ATTACK_DURATION)
        return True
    
    def perform_liberation(self):
        """大招释放及后续连击流程"""
        if self.resonance_available():
            self.click_resonance()
        if self.echo_available():
            self.click_echo(time_out=0)   
        self.f_break()
        self.perform_enhanced_heavy()
        
        if self.liberation_available():
            self.click_liberation(send_click=True, wait_if_cd_ready=self.LIB_CD_WAIT)
            self.record_liberation_use()
            self.logger.info('Lucy perform lib: Started')
            
            for _ in range(self.LIB_CLICK_COUNT):
                self.click()
                self.sleep(self.CLICK_INTERVAL, check_combat=False)
                
            self.logger.info('Lucy perform lib: Ended')
            
        self.logger.debug("Liberation not available, skipping.")
        return True

    def perform_enhanced_heavy(self):
        """强化重击执行逻辑"""
        if self.is_mouse_forte_full():
            self.heavy_attack(self.HEAVY_ATTACK_DURATION)
            self.logger.info('Lucy perform enhanced heavy attack 1')
            self.sleep(self.ENHANCED_HEAVY_INTERVAL, check_combat=False)
            
            self.heavy_attack(self.HEAVY_ATTACK_DURATION)
            self.logger.info('Lucy perform enhanced heavy attack 2')