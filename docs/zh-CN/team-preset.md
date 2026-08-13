# 队伍预设 (Team Preset)

队伍预设让你把"一套队伍 + 每个角色的参数/自定义代码 + 可选的队伍级出招逻辑"打包成一个可复用的团队配置。任务运行时,程序识别出你当前的游戏队伍,自动套用匹配的预设。

## 基础概念

- **预设 (Preset)**:一个队伍配置,包含名称、简介、1~3 个角色槽位。
- **槽位 (Slot)**:一个角色位置,可锁定角色、勾选全局参数(如 `Iuno C6`)、附加该角色的自定义代码。
- **必选 (Required)**:勾选后,该角色必须在你的游戏队伍中,这个预设才会被自动匹配。适合"少了某角色这套就没法打"的队伍。
- **强制 (Force This Team)**:忽略自动匹配,任务始终使用该预设(即使队伍不符合)。
- **队伍逻辑 (Team Logic)**:可选。为一个预设写一个 `BaseTeamCombat` 子类,用它完全替代三个角色的独立出招,实现协奏循环、爆发窗口等队伍级操作。

## 匹配规则

任务启动或队伍变化时,程序按以下顺序决定用哪套配置:

1. **强制预设**:如果你点了 "Force This Team",直接用该预设(此时忽略自动匹配和必选)。
2. **自动匹配**:遍历所有勾选 "Auto match in-game team" 的预设,按**匹配分数**选最优:
   - 分数 = 命中启用角色数 ÷ 该预设启用的角色总数,全匹配 = 100%。
   - **必选角色不在你的队伍中 → 该预设直接淘汰**(记为 0 分)。
   - 同分时取列表顺序靠前的预设(列表里可 Move Up / Move Down 调优先级)。
   - 命中全部角色的预设优先于只命中一部分的预设。
3. **全局配置**:没有任何预设匹配时,回退到全局 Character Config。

未匹配时,顶部状态条会显示每个预设的评分和缺失的必选角色(tooltip 可看详情),任务日志也会输出同样的摘要,方便排查"为什么没匹配上"。

## 使用流程

1. 打开 **Team Preset** 标签页。
2. 点 **From Template** 选一个内置模板(如 *Concat Cycle* 协奏循环流、*Echo Opening* 声骸起手流),或点 **New** 手动创建。
3. 在每个槽位里选角色,勾选需要的全局参数;需要硬性绑定就勾 **Required**。
4. 可选:点 **Team Logic** 写队伍级出招逻辑(编辑器里有 **API Quick Ref** 速查可用接口)。
5. 游戏内队伍满足条件时自动生效;想让任务无视队伍变化就用 **Force This Team**。

## 队伍逻辑示例

```python
class MyTeamLogic(BaseTeamCombat):
    def perform(self):
        me = self.current_char          # 当前在场角色
        if me is None:
            return
        i = me.index
        if self.liberation_available(i):
            self.click_liberation(i)
            return
        if self.con_full(i):            # 协奏值满,切走
            self.switch_next_char(i)
            return
        self.click(i)                   # 普攻
```

常用能力:`switch_to(i)` 直接切人、`con_percent(i)` 协奏 0~1、`cd_remaining(i, 'resonance')` 剩余冷却、`char_is(i, 'Verina')` 判断角色。完整清单见编辑器内的 **API Quick Ref**。

## 模板与分享

- 内置模板位于仓库 `presets/` 目录,可参考其 `preset.json` 格式自己添加。
- 点 **Export** 把预设(含自定义代码与队伍逻辑)导出为 JSON;别人 **Import** 即可安装。
- 槽位 JSON 支持 `"required": true` 标记必选角色;`"char": ""` 表示不锁定角色,安装后自己填。

## 存储与恢复

- 预设数据保存在 `configs/team_presets/index.json`(索引)+ 每个预设一个文件夹(角色代码、队伍逻辑等)。
- 每个预设还会在自己的文件夹里保留一份 `preset.json` 元数据备份;索引丢失或损坏时会自动从这些备份重建,预设不会丢。
