import time

from src.char.BaseChar import BaseChar


class Lucilla(BaseChar):
    """Lucilla 自动战斗: 回路充能型 + 大招变身型角色。

    机制: 长按 E 或蓄力重击各攒 1 格回路能量, 攒满 3 格大招可用; 放大招后变身进入特殊形态
    (技能栏/大招图标消失, 视觉信号全失效), 固定时长输出后变回原建模, 再切人。
    """
    HOLD_TIME: float = 1.4
    LIBERATION_ANIMATION_TIME: float = 3.0
    LIBERATION_HEAVY_TIME: float = 6.8
    CHARGE_TIME_OUT: float = 8.5
    LIBERATION_CD_SKIP: float = 1.5

    def do_perform(self):
        if not self.perform_combat():
            self.switch_next_char()

    def perform_combat(self):
        """攒能量 -> 大招可用则放大招接输出.

        Returns:
            bool: 放出了大招(并已在 perform_liberation 内切人)返回 True, 否则 False.
        """
        start = time.time()

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=2.0)
        self.task.next_frame()

        if self.try_liberation():
            return True

        while time.time() - start < self.CHARGE_TIME_OUT:
            if self.try_liberation():
                return True

            self.charge_once()

            if self.try_liberation():
                return True

            if self.energy_full_but_lib_on_cd():
                self.logger.info('Lucilla energy full but liberation on cd, switch to save time')
                break

        return False

    def charge_once(self):
        """攒 1 格回路能量: E 可用优先长按 E、否则蓄力重击, 长按动作完整结束后再闪避.

        闪避放在长按动作**之后**(而非之前): 长按完整结束才闪, 闪避绝不会打断正在进行的长按;
        闪避也作为本格与下一格长按之间的过渡/规避. 两个长按内部 sleep 均 check_combat=False,
        长按动作内部 sleep 均 check_combat=False, 不会被战斗误判打断, 且已推进帧重置 scene.cd_refreshed, 故攒完读 CD/能量即为最新值.
        """
        if self.resonance_available():
            if self.hold_resonance(self.HOLD_TIME):
                self.dodge()
        else:
            if self.hold_heavy_attack(self.HOLD_TIME):
                self.dodge()

    def dodge(self):
        """向左闪避(规避敌人攻击). 只在长按动作完整结束后由 charge_once 调用, 故不会打断长按."""
        self.task.send_key_down('a')
        try:
            self.task.send_key(self.task.key_config['Dodge Key'], after_sleep=0.05)
        finally:
            self.task.send_key_up('a')

    def try_liberation(self):
        """大招就绪则放招(顺带先放声骸), 返回是否放出。"""
        if not self.liberation_available():
            return False
        else: 
            if self.echo_available():
                self.click_echo(time_out=0)
            self.perform_liberation()
            self.switch_next_char()
        return True

    def energy_full_but_lib_on_cd(self):
        """解放图标高亮但仍在较长 CD 中, 返回 True 表示该切人而非继续攒能量。

        liberation_available() 把"能量满"和"无CD"绑在一起判断, 故用 check_cd=False 单看能量满.
        """
        energy_full = self.available('liberation', check_color=True, check_cd=False)
        return energy_full and self.task.get_cd('liberation') > self.LIBERATION_CD_SKIP

    def perform_liberation(self):
        """放大招进入变身形态, 按住左键固定时长输出后由调用方切人.

        不调用 BaseChar.click_liberation(): 它内部 ``while not in_team()`` 在变身形态下会因
        in_team 误判卡死到 7s 超时抛异常. 这里自己发解放键, 用 liberation_available() 变 False
        (大招图标消失 = 已进入形态) 作为放出信号.

        """
        if not self.task.use_liberation:
            return

        start = time.time()
        while self.liberation_available() and time.time() - start < 1.5:
            self.send_liberation_key()
            self.sleep(0.1, check_combat=False)
        self.record_liberation_use()
        self.logger.info('Lucilla perform lib')

        self.sleep(self.LIBERATION_ANIMATION_TIME, check_combat=False)
        self.task.mouse_down()
        try:
            self.sleep(self.LIBERATION_HEAVY_TIME, check_combat=False)
        finally:
            self.task.mouse_up()

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=3.0)
        self.logger.info('Lucilla perform lib end')

    def hold_heavy_attack(self, duration):
        """按住左键蓄力重击一段时间 (攒 1 格回路能量)。

        不用 BaseChar.heavy_attack: 它内部 sleep(duration) 默认带战斗检查, 蓄力期间某帧
        in_combat() 误判就抛 NotInCombatException 打断蓄力. 这里 check_combat=False 保证不被打断.
        """
        self.task.mouse_down()
        try:
            self.sleep(duration, check_combat=False)
        finally:
            self.task.mouse_up()

    def hold_resonance(self, duration):
        """长按共鸣技能键一段时间 (攒 1 格回路能量)。"""
        start = time.time()
        self.task.send_key_down(self.get_resonance_key())
        try:
            while time.time() - start < duration:
                self.check_combat()
                self.task.next_frame()
        finally:
            self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()
