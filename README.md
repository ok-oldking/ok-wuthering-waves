# 声骸评分

一个基于 [OK Script](https://github.com/ok-oldking/ok-script) 与
[OKWW](https://github.com/ok-oldking/ok-wuthering-waves) 窗口捕获能力的独立鸣潮声骸评分工具。

程序只读取游戏窗口画面，通过 OCR 识别“查看单个声骸”和“调谐单个声骸”界面的
两条主词条与最多五条副词条，并使用 XW-UID 角色模板实时显示：

- 每条词条贡献分和副词条档位；
- 当前评分与理论最高分；
- 红色主词条框、白色副词条框和 `ECHO-ON` 状态。

属性详情、声骸汇总页和其他游戏画面不会触发评分。游戏退到后台时，最后一次结果仍会保留。

## 开发运行

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main_debug.py
```

也可以运行 `start_personal_debug.cmd`。鸣潮以管理员权限运行时，本程序会申请相同权限。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "Test*.py"
```

## 构建

仓库使用 `pyappify.yml` 生成 China/Global Windows 安装包。发布产物统一使用
`echo-score-win32-*-setup.exe` 命名。

## 更新 XW-UID 评分模板

完整的仓库职责、脚本选项、三目录同步要求和已验证发布记录见
[声骸评分维护与分发](docs/echo-score-maintenance.md)。

在本仓库目录运行，检查上游的新角色、多模态模板和已有评分权重变化：

```powershell
.\.venv\Scripts\python.exe scripts\update_xwuid_echo_templates.py --check
```

完整同步、打包并提交推送两个仓库：

```powershell
.\.venv\Scripts\python.exe scripts\update_xwuid_echo_templates.py --publish --commit-push
```

脚本从 XW-UID 的独立资源仓库拉取全部 `calc*.json` 和 `condition.json`，
保留每个角色的所有模态，并报告新增、修改、删除的模板。资源缓存默认位于
`E:/xwuid-score-resources`；首次运行会自动克隆，只检出评分 JSON 文件。

发布时自动运行测试、递增补丁版本、生成 `.okscript` 和导入文件夹，同步到
本仓库 `echo-score/`、`D:/ok-ww/data/apps/ok-ww/working/ok_import/echo-score/` 和
`E:/okww-xwuid-echo-score/echo-score/`，重建并验证 `echo-score.zip`、更新分发 README，
最后 commit & push 两个仓库。无变化时跳过发布；使用 `--force-package` 可以强制重打包。

`--publish` 不带 `--commit-push` 时仅生成本地产物，便于检查差异。
不带选项时只拉取并更新源码快照。`--distribution`、`--install-dir` 可指定其他目录；
`--version` 可指定发布版本。提交推送模式要求两个仓库均无未提交修改；失败会明确报错，
不会忽略测试、复制或推送错误。运行后重启 OKWW 加载新模板。

## 声明

本项目不会读取游戏内存或修改游戏文件。使用任何外部辅助工具均可能存在账号风险，
请自行判断并承担后果。项目继承上游 AGPL-3.0 许可，相关版权与来源见 [LICENSE.txt](LICENSE.txt)。
