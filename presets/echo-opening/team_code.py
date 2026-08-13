class EchoOpeningLogic(BaseTeamCombat):
    """声骸起手流:每次换人进场先用声骸起手,再按协奏循环推进。

    规则(自上而下,每 tick 只做一个动作):
      - 共鸣解放就绪 → 立刻放
      - 声骸就绪 → 声骸起手(优先于共鸣,适合叠势/触发协同的声骸)
      - 共鸣技能就绪 → 放共鸣技能
      - 当前角色协奏值满 → 切走
      - 其余时间普攻

    如果某个角色的声骸更适合收尾而不是起手,把它从第二位挪到
    共鸣技能后面即可;协奏满切人用 switch_next_char 或直接 switch_to(i)。
    """

    def perform(self):
        me = self.current_char                # 当前在场角色
        if me is None:
            return
        i = me.index
        if self.liberation_available(i):      # 共鸣解放就绪
            self.click_liberation(i)
            return
        if self.echo_available(i):            # 声骸就绪:起手
            self.click_echo(i)
            return
        if self.resonance_available(i):       # 共鸣技能就绪
            self.click_resonance(i)
            return
        if self.con_full(i):                  # 协奏值满,切走灌能量
            self.switch_next_char(i)
            return
        self.click(i)                         # 普攻
