class EchoBurstLogic(BaseTeamCombat):
    """声骸爆发开场:上场先声骸 + 共鸣技能 + 解放把爆发打满。

    之后进入协奏循环(副C 灌能量 → 爆发位收尾),并演示用
    switch_to 把奶妈切上来保命(示例逻辑,可按需删改)。

    规则(每 tick 只做一个动作):
      - 声骸就绪 → 放声骸
      - 共鸣解放就绪 → 放解放
      - 共鸣技能就绪 → 放共鸣技能
      - 协奏值满 → 切副C 灌能量,满了切回爆发位
      - 其余时间普攻

    安装后把三个槽位填成你的角色即可。
    """

    def perform(self):
        me = self.current_char
        if me is None:
            return
        i = me.index
        if self.echo_available(i):            # 声骸优先:开场爆发
            self.click_echo(i)
            return
        if self.liberation_available(i):      # 解放跟上
            self.click_liberation(i)
            return
        if self.resonance_available(i):
            self.click_resonance(i)
            return
        if self.char_is(i, 'Verina') or i == 2:
            self._support(i)                  # 奶妈位:协奏满就切回爆发位
            return
        if self.con_full(i):
            self.switch_to(1)                 # 爆发位协奏满 → 切副C
            return
        self.click(i)

    def _support(self, i):
        if self.con_full(i):
            self.switch_to(0)                 # 奶妈协奏满 → 切回爆发位
            return
        self.click(i)