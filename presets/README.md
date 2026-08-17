# 内置队伍预设模板

本目录存放内置模板,TeamPreset 页的 **From Template** 按钮会扫描这里,一键安装为新预设(可重复安装,自动去重)。

## 如何添加一个模板

1. 新建文件夹 `presets/<模板名>/`
2. 放入 `preset.json`(与导出的队伍预设 JSON 格式完全一致,见下)
3. 可选:`team_code.py`(队伍出招逻辑)或任意 `<角色名>.py`(角色自定义代码)放在同一文件夹,安装时会自动打包进预设
4. 可选:在 `preset.json` 顶层加 `"description"` 字段,选择模板时会显示

## preset.json 格式

```json
{
  "type": "ok_ww_team_preset",
  "version": 1,
  "name": "模板显示名",
  "description": "模板简介(可选)",
  "preset": {
    "id": "模板内部 id",
    "name": "预设名",
    "note": "",
    "created_from": "builtin template",
    "auto_match": true,
    "description": "预设简介(可选)",
    "slots": [
      { "char": "Iuno", "enabled": true, "note": "主C", "params": {}, "custom_code": "" }
    ]
  }
}
```

- `"char"` 为空表示"不锁定角色",玩家安装后自己填。
- `"custom_code"` 内嵌脚本也可,直接写 `.py` 文件更直观。
- 槽位可选 `"required": true`,标记为必选角色:只有该角色在队伍中时该预设才会被自动匹配(强制选择不受影响)。

## 现有模板

| 模板名 | 说明 |
| --- | --- |
| `quick-start` | 通用示例:谁在场看谁,技能好了就放,协奏满切人 |
| `concat-cycle` | 协奏循环流:主C/副C轮流站场,协奏满即切,共鸣冷却时重击积回路 |
| `echo-opening` | 声骸起手流:换人进场优先声骸起手,再接共鸣输出 |
| `intro-cycle` | 入场技循环流:switch_to 轮换 + wait_intro 等入场技,形成三角色闭环 |
| `echo-burst` | 声骸爆发开场:先声骸→共鸣→解放打爆发,再切奶妈/副C 循环 |
