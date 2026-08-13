class ConcatCycleLogic(BaseTeamCombat):
    """协奏循环流:主C/副C轮流站场,协奏(变奏)值满即切人。

    规则(自上而下,每 tick 只做一个动作):
      - 共鸣解放就绪 → 立刻放(不切人)
      - 声骸就绪 → 放声骸
      - 共鸣技能就绪 → 放共鸣技能
      - 当前角色协奏值满 → switch_next_char 按优先级切人
      - 共鸣技能还在冷却且协奏过半 → 重击(长按)积回路
      - 其余时间普攻

    安装后把三个槽位填成你的角色即可,想调整优先级直接改 perform()。
    常用查询:con_percent(i) 协奏 0~1、cd_remaining(i, 'resonance') 冷却秒数。
    """

    def perform(self):
        me = self.current_char                # 当前在场角色
        if me is None:
            return
        i = me.index
        if self.liberation_available(i):      # 共鸣解放就绪
            self.click_liberation(i)
            return
        if self.echo_available(i):            # 声骸就绪
            self.click_echo(i)
            return
        if self.resonance_available(i):       # 共鸣技能就绪
            self.click_resonance(i)
            return
        if self.con_full(i):                  # 协奏值满,切走灌能量
            self.switch_next_char(i)
            return
        con = self.con_percent(i)
        if con is not None and con >= 0.5 and self.cd_remaining(i, 'resonance') > 3:
            self.heavy_click_forte(i)         # 共鸣冷却中:重击积回路
            return
        self.click(i)                         # 普攻
