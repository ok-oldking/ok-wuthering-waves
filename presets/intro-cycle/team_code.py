class IntroCycleLogic(BaseTeamCombat):
    """入场技循环流:主C → 副C → 奶妈 → 主C 循环轮换。

    核心是 switch_to:由脚本自己决定切谁(不走优先级选人),
    配合 wait_intro 等入场技播完再出招,适合协奏轮换型队伍。

    规则(每 tick 只做一个动作):
      - 共鸣解放就绪 → 立刻放
      - 声骸就绪 → 放声骸
      - 共鸣技能就绪 → 放共鸣技能
      - 当前角色协奏值满 → 切到下一个轮换位
      - 入场技正在播 → 等它播完
      - 其余时间普攻

    安装后把三个槽位填成你的角色即可。
    """

    def perform(self):
        me = self.current_char
        if me is None:
            return
        i = me.index
        if self.liberation_available(i):
            self.click_liberation(i)
            return
        if self.echo_available(i):
            self.click_echo(i)
            return
        if self.resonance_available(i):
            self.click_resonance(i)
            return
        if self.con_full(i):
            self.switch_to(self._next(i))   # 协奏满,切到下一个轮换位
            return
        if self.wait_intro(i):              # 正在播入场技:等播完
            return
        self.click(i)                       # 普攻

    def _next(self, index):
        """返回下一个轮换位:0 → 1 → 2 → 0。"""
        return (index + 1) % 3