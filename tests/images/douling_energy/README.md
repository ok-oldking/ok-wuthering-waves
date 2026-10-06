# 卜灵能量条识别样本与验收

独立识别模块为 `src/utils/douling_energy.py`，尚未接入角色战斗逻辑。
输入为游戏客户区 BGR `uint8` 截图，调用方通过 `hud_visible` 确认当前
显示卜灵 HUD；仅有队伍 UI 不足以确认正在显示卜灵的能量条。

少阳（左侧黄色）和少阴（右侧蓝色）各自只有有/无两种状态。四张用户
截图覆盖全部正常组合，不存在部分能量或能量百分比场景。

| 原始附件 | 预期 state |
| --- | --- |
| none_shaoyin_shaoyang.png | none |
| shaoyang.png | shaoyang |
| shaoyin.png | shaoyin |
| shaoyin_and_shaoyang.png | both |

原图均为 1920×1080，按字节复制，`manifest.json` 记录来源、预期结果和
SHA-256。红框仅为用户辅助定位的人工标注，实际游戏没有红框。
算法不检测、追踪或去除红框，采样区域不覆盖标注。

## 接口

```python
from src.utils.douling_energy import recognize_energy

result = recognize_energy(frame, hud_visible=True)
# result.state: 'none' / 'shaoyang' / 'shaoyin' / 'both'
# result.state 为 None 时，result.reason 给出失败原因。
```

`hud_hidden` 表示调用方确认 HUD 不可见；`invalid_frame` 表示无效输入或
采样区域尺寸不足；`bar_not_visible` 表示至少一侧采样区域缺少足够的
明亮刻度/能量像素。这些失败不是第五种正常状态，也不能当作 `none`。
局部亮度检查能排除空白和部分遮挡，但不能证明所有未知画面都是卜灵
HUD，仍需调用方确认。函数不修改输入帧、不刷新截图、不等待、不发送
输入、不写日志或保存图片。

## 区域与判断规则

参考分辨率为 1920×1080，坐标格式为 `(x, y, width, height)`：

- 少阳：`(813, 980, 110, 27)`。
- 少阴：`(978, 980, 112, 27)`。

区域按 `min(width / 1920, height / 1080)` 等比缩放，水平居中并按底边
锚定，避开中央阴阳图案和下方血条。

左右分别判断目标颜色，再组合四种状态。所有通道差以有符号整数计算：

- 黄色：`R > 130`、`R - B > 35`、`G - B > 20`。
- 蓝色：`B > 130`、`B - R > 35`、`B - G > 10`。
- 目标像素占采样区域至少 0.15，且至少 0.60 的列中目标像素占比大于
  0.10，才判定该侧存在能量，避免局部光点引起误判。
- 区域需有至少 0.03 的像素最大通道值大于 130，且至少 0.30 的列中
  此类亮像素占比大于 0.10，否则返回 `bar_not_visible`。

四张原图中，有少阳时左侧黄色占比约为 0.69～0.71，有少阴时右侧蓝色
占比约为 0.85，空条目标颜色占比最高约为 0.003。数值仅为内部颜色
证据，不代表游戏能量百分比。阈值根据这些样本确定，四张原图属于开发
和回归样本，不是独立盲测集。

## 验证

仓库存在 `.venv` 时优先使用其 Python，例如 Windows：

```powershell
.\.venv\Scripts\python.exe -B -m unittest tests.TestDoulingEnergy tests.TestGuaxiang tests.TestDouling tests.TestCustomCharLoader -v
```

不存在本地虚拟环境时使用 `python`。日志写权限受限时可设置项目已有的
`OK_DISABLE_FILE_LOG=1`。

测试覆盖四张原图、哈希、重复识别、帧只读、HUD 隐藏、异常输入、空白及
遮挡、区域内无红框、区域外内容变化、局部彩色光点、人工缩放至
720p/1080p/1440p，以及人工宽屏/高屏的居中与底边锚定。
修改区域外全部像素用于验证识别不依赖红框，不等同于真实无标注实机
截图验证。人工缩放和补边只验证坐标/采样，实机动画、UI 缩放及不同
分辨率的截图验证尚待后续进行。
