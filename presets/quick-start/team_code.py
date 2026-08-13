class QuickStartLogic(BaseTeamCombat):
    """示例队伍逻辑:谁在场看谁,技能好了就放,协奏值满就切人。

    保存后该预设启用队伍级出招:三个角色不再各自出招,
    而是统一由这里的 perform() 决定。可继续在下方扩展,
    常用能力:switch_to(index) 直接切人、con_percent / cd_remaining
    查询状态、char_is(index, 'Verina') 判断角色。
    """

    def perform(self):
        me = self.current_char              # 当前在场角色
        if me is None:
            return
        i = me.index
        if self.liberation_available(i):    # 共鸣解放就绪
            self.click_liberation(i)
            return
        if self.echo_available(i):          # 声骸就绪
            self.click_echo(i)
        if self.resonance_available(i):     # 共鸣技能就绪
            self.click_resonance(i)
            return
        if self.con_full(i):                # 协奏值满,切走
            self.switch_next_char(i)
            return
        self.click(i)                       # 普攻
