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

## 声明

本项目不会读取游戏内存或修改游戏文件。使用任何外部辅助工具均可能存在账号风险，
请自行判断并承担后果。项目继承上游 AGPL-3.0 许可，相关版权与来源见 [LICENSE.txt](LICENSE.txt)。
