# 声骸评分 OK Script

这是可导入官方 OKWW/OK Script 安装版的声骸评分适配包。

构建：

```powershell
.\.venv\Scripts\python.exe scripts\build_echo_score_okscript.py
```

产物位于 `dist/echo-score.okscript`。在官方 OKWW 的“脚本”页导入该文件，
然后在“声骸评分设置”任务卡中启用评分即可。

如果要直接复制文件，使用 `dist/echo-score/` 文件夹，将整个文件夹复制到：

`D:\ok-ww\data\apps\ok-ww\working\ok_import\echo-score`

重启 OKWW 后即可加载。

本包不覆盖宿主程序源码，只注册一个设置任务和一个隐藏后台识别任务。
