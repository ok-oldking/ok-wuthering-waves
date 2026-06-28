import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Lucilla(BaseChar):
    """Lucilla 自动战斗: 回路充能型 + 大招变身型角色。

    机制: 长按 E 或蓄力重击各攒 1 格回路能量, 攒满 3 格大招可用; 放大招后变身进入特殊形态
    (技能栏/大招图标消失, 视觉信号全失效), 固定时长输出后变回原建模, 再切人。
    """
    # 单次长按/蓄力时长 (秒): 长按 E 或蓄力重击各攒 1 格回路能量.
    HOLD_TIME: float = 1.4
    # 大招变身动画时长 (秒): 这段不可操作, 普攻无效, 先等过去
    LIBERATION_ANIMATION_TIME: float = 3.0
    # 变身后重击时长 (秒)
    LIBERATION_HEAVY_TIME: float = 5.8
    # 攒能量阶段的整体上限 (秒), 防止攒不满时死循环
    CHARGE_TIME_OUT: float = 7.2
    LIBERATION_CD_SKIP: float = 1.5
    # 切回本角色后等技能栏渲染稳定的时长 (秒): 切回首帧技能栏 UI 渲染晚, 读 liberation 会读假
    SWITCH_IN_SETTLE: float = 0.5

    def do_perform(self):
        if not self.perform_combat():
            self.switch_next_char()

    def perform_combat(self):
        """攒能量 -> 大招可用则放大招接输出.

        Returns:
            bool: 放出了大招(并已在 try_liberation 内切人)返回 True, 否则 False.
        """
        start = time.time()

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=0.8)
        self.sleep(self.SWITCH_IN_SETTLE, check_combat=False)  # 等技能栏渲染稳定再判大招
        self.task.next_frame()

        if self.try_liberation():
            return True

        while time.time() - start < self.CHARGE_TIME_OUT:
            # 能量满但放不出(短CD / 切回UI未渲染读假 / 任何原因) -> 别溢出空攒, 直接切人
            if self.energy_full() and not self.liberation_available():
                self.logger.info('Lucilla energy full but liberation not castable, switch')
                break

            # 能量没满且大招在较长 CD -> 没必要攒, 切人省时间
            if not self.liberation_available() and self.task.get_cd('liberation') > self.LIBERATION_CD_SKIP:
                self.logger.info('Lucilla liberation on long cd, switch to save time')
                break    

            if self.try_liberation():
                return True

            self.charge_once()

        return False

    def charge_once(self):
        """攒 1 格回路能量: E 可用优先长按 E、否则蓄力重击.
        """
        if self.resonance_available():
            self.hold_resonance(self.HOLD_TIME)
        else:
            self.heavy_attack(self.HOLD_TIME)
        self.task.next_frame()

    def try_liberation(self):
        """大招就绪则放招(顺带先放声骸), 返回是否放出。

        仅在大招可用(能量满且无CD)时才放招; 未就绪只返回 False, 由外层(perform_combat 循环)
        统一处理攒能量/长CD切人。不能用"非长CD就放"——那会在能量没满时空放声骸/大招。
        """
        if not self.liberation_available():
            return False

        if self.echo_available():
            self.click_echo(time_out=0)
            
        self.perform_liberation()
        self.switch_next_char()
        return True

    def energy_full(self):
        """回路能量是否已满(解放图标高亮, 忽略CD)。

        liberation_available() 把"能量满"和"无CD"绑在一起判断, 故用 check_cd=False 单看能量满,
        配合 not liberation_available() 即可识别"能量满但放不出(短CD/切回读假等)"而切人, 不攒溢出。
        """
        return self.available('liberation', check_color=True, check_cd=False)

    def perform_liberation(self):
        """放大招进入变身形态, 按住左键固定时长输出后切人.

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
        if not self.has_short_action():
            self.heavy_attack(self.LIBERATION_HEAVY_TIME)

        self.logger.info('Lucilla perform lib end')

    def hold_resonance(self, duration):
        """长按共鸣技能键一段时间 (攒 1 格回路能量)。

        长按期间用 check_combat=False: 攒能量在正常态, in_combat() 偶发误判不应打断长按;
        sleep 已推进帧, 无需忙等/额外 next_frame。
        """
        self.task.send_key_down(self.get_resonance_key())
        try:
            self.sleep(duration, check_combat=False)
        finally:
            self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_verina', 'char_shorekeeper'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)