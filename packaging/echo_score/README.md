# 声骸评分 OK Script

这是声骸评分功能的可安装适配层。计分规则取自项目内唯一的纯逻辑实现
`src/echo_score.py`，安装包不会复制出另一套需要单独维护的规则。

## 构建

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\build_echo_score_okscript.py
```

产物为 `dist/echo-score.okscript`。在支持“导入脚本”的 OKWW 版本中选择该文件，
重启或刷新自定义任务后启用“声骸评分”任务即可。

导入后，“声骸评分”页面会显示一个“声骸评分设置”任务卡。后台识别任务默认启用并隐藏，
所有选项都在这个设置卡中修改；卡片上的“运行”按钮只用于确认设置已经应用。

## 兼容性

- 要求宿主提供 `TriggerTask`、OCR 和原生 overlay API。
- 安装包不依赖本仓库的 `src` 包，也不会覆盖宿主源码。
- 标准 OK Script 配置目前只提供普通下拉框；搜索式角色选择器属于本 fork 的 UI 增强，
  宿主未实现可编辑下拉框时会自动退化为完整的模板列表。
