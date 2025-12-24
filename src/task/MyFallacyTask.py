from src.task.FarmEchoTask import FarmEchoTask
from ok import Logger

logger = Logger.get_logger(__name__)

class MyFallacyTask(FarmEchoTask):   
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def manage_boss_interactions(self):
        if self.in_combat():
            return
        boss = self.config.get('Boss')
        
        # 核心修改點：針對『無歸的謬誤』採用自訂圖鑑搜尋與保底邏輯
        if boss in ('Fallacy of No Return'):
            self.aim_boss = "無歸的謬誤" 
            
            # 1. 執行初步偵測與傳送
            if not self.find_f_with_text() and not self.in_combat():
                self.log_info(f"偵測到目標為 {boss}，啟動自訂圖鑑傳送流程...")
                self.teleport_to_nearest_boss() 
                self.sleep(2) # 等待傳送載入
                
                if not self.in_combat():
                    self.log_info("執行微調：強制向右修正角度...")
                    # 強制執行 0.15 秒的右偏位移 [cite: 2025-10-18]
                    self.run_until(lambda: False, 'd', time_out=0.15, running=True)
                    self.sleep(0.2)
                    
                    self.log_info("修正完成，開始前進尋找 F 鍵...")
                    # 執行前進搜尋 [cite: 2025-10-18]
                    self.run_until(lambda: self.in_combat() or self.find_f_with_text(), 'w', time_out=8, running=True)
            
            # 2. 核心保底：如果走完還是沒看到 F，直接再次傳送並返回 [cite: 2025-10-18]
            if not self.in_combat() and not self.find_f_with_text():
                self.log_error("仍找不到按鈕，執行緊急重新傳送以重置座標...")
                self.teleport_to_nearest_boss()
                self.sleep(2)
                return # 立即退出，讓下一輪主迴圈重新判斷 [cite: 2025-10-18]
            
            # 3. 正常處理後續的點擊啟動
            if self.walk_until_f(time_out=15, check_combat=True, running=True):
                self.scroll_and_click_buttons()
            return 
            
        # 如果不是目標 Boss，執行父類別（原作者）的原始邏輯
        super().manage_boss_interactions()
