# 卦象识别样本与验收

`manifest.json` 记录全部 11 张用户原始截图的路径、预期序列、附件名及
SHA-256。原图按字节复制，未去除红框、改变颜色或压缩尺寸。

两个模板来源图保存在 `assets/images/douling_gua_blue.png` 和
`assets/images/douling_gua_yellow.png`，其余九张在本目录。
COCO 标签为 `douling_gua_blue`、`douling_gua_yellow`，两处真实主体标注均为
1600×900 参考画面中的 `[782, 746, 21, 27]`。

| 样本 | 预期序列 | 用途 |
| --- | --- | --- |
| blue1_grass | 蓝 | 草地背景 |
| mixed4 | 黄、蓝、蓝、蓝 | 混合颜色与顺序，保留用户辅助红框 |
| blue4 | 蓝、蓝、蓝、蓝 | 弱光与强光圈 |
| blue3 | 蓝、蓝、蓝 | 数量变化 |
| blue2 | 蓝、蓝 | 明亮背景与连接光效 |
| empty | 空列表 | 无卦象负样本 |
| blue1 | 蓝 | 蓝色模板来源，自检 |
| yellow4 | 黄、黄、黄、黄 | 弱光与强光圈 |
| yellow1 | 黄 | 黄色模板来源，自检 |
| yellow2 | 黄、黄 | 强光圈与明亮背景 |
| yellow3 | 黄、黄、黄 | 明亮背景与数量变化 |

实现位于 `src/utils/guaxiang.py`。只在
`configs/custom_teams/Carlotta__Douling__Zhezhi/Douling.py` 的入场等待之后、
第一下固定轴普攻之前识别一次，只记录结果。
跳 a 完成后刷新画面并识别：只有确认四个卦象才执行原有重击、声骸、大招及
切人。少于四个或结果不确定时，沿用 0.3 秒间隔普攻，然后刷新画面、重新识别，
直至确认四个；不重复开头的 E 或跳跃，也不因等待超时而直接放行。
补卦象期间恢复正常退战检查，退战或手动停止任务可中断循环。
日志前缀为 `[DoulingRecognition]`；正常输出 `count`、`sequence` 和
`elapsed_ms`，不确定时输出 `status=uncertain` 及原因。调试模式绘制搜索框、
候选框、形状与颜色分数。

每次识别还会把同一帧交给项目后台截图队列，以 `show_box=False` 保存原图，
不重新取图或等待写盘。沿用项目的截图脱敏设置。入场标识为 `entry`，重击前为
`before_heavy`，日志中的 `screenshot_name=guaxiang/<标识>_<唯一编号>` 与文件名
对应。当前配置的保存目录为 `screenshots/guaxiang/`，实际文件名由框架添加时间
前缀和 `_original.png` 后缀。此日志表示已请求保存，后台写盘仍可能失败；
提交截图请求失败时会记录 `[DoulingScreenshot]`，不改变识别结果或满四个的门槛。
`[DoulingGuaxiang]` 日志记录 `action=normal_attack` 或 `action=continue_to_heavy`。

无候选且调用方确认 HUD 有效时返回 `[]`；隐藏 HUD、无效截图、缺失资源、
弱匹配、颜色冲突或超过四个候选返回 `None`。这不保证所有未知场景都能检测
出漏检或遮挡，需要继续通过真实截图和实战日志验证。

运行：优先使用仓库 `.venv` 的 Python；没有本地虚拟环境时运行：

```powershell
python -B -m unittest tests.TestGuaxiang tests.TestCustomCharLoader -v
```

测试覆盖原图、人工缩放、人工宽屏居中、区域内平移、错误颜色、重复候选、
五个符文、无效输入、真实队伍 HUD 模板，以及实际队伍类的两段固定轴。
队伍目录被 Git 忽略，在未安装该本地队伍的检出中，队伍接入测试会明确跳过。
截图识别测试仍正常运行。

初次验证全部 11 张原图通过，其中两张为模板来源自检、九张为其他截图回归；
其他截图也参与了方案调试，因此这不是独立盲测集。人工缩放至 720p、1080p、
1440p 和人工加宽只能验证坐标/插值，不能代替对应分辨率、UI 缩放及动画状态
的实机验证。缓存后纯识别约 0.6 ms，首次解码模板原图约 71 ms，耗时随设备变化，
不包括游戏截图采集；队伍日志还包含 HUD 检查耗时。
