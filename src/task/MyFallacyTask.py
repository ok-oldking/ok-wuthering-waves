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
        
        # 核心修改點：針對『無歸的謬誤』採用圖鑑搜尋
        if boss in ('Fallacy of No Return'):
            self.aim_boss = "無歸的謬誤" # 設定搜尋關鍵字
            
            # 如果目前沒看到互動鍵且不在戰鬥，執行 F2 圖鑑傳送
            if not self.find_f_with_text() and not self.in_combat():
                self.log_info(f"偵測到目標為 {boss}，啟動自訂圖鑑傳送流程...")
                self.teleport_to_nearest_boss() 
                self.sleep(3)
                if not self.in_combat():
                    self.log_info("執行微調：強制向右修正角度...")
                    
                    # 使用一個永遠不會達成的條件 (lambda: False)，配合 time_out 
                    # 這樣它就一定會強制執行足夠的秒數 [cite: 2025-10-18]
                    self.run_until(lambda: False, 'd', time_out=0.25, running=True)
                    
                    self.log_info("修正完成，開始前進...")
                    # 這裡才放真正的停止條件 [cite: 2025-10-18]
                    self.run_until(lambda: self.in_combat() or self.find_f_with_text(), 'w', time_out=8, running=True)
            # 傳送後向前走以觸發 Boss
            if not self.in_combat():
                self.run_until(lambda: self.in_combat() or self.find_f_with_text(), 'w', time_out=8, running=True)
            
            # 處理後續的點擊啟動
            if self.walk_until_f(time_out=15, check_combat=True, running=True):
                self.scroll_and_click_buttons()
            return # 執行完自訂邏輯後直接返回，不跑下面的原作者邏輯
            
        # 如果不是『無歸的謬誤』，則執行父類別（原作者）的原始邏輯
        super().manage_boss_interactions()
