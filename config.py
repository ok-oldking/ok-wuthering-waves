"""Minimal OK Script configuration for the standalone Echo Score app."""

import os
import re
from pathlib import Path

from ok import ConfigOption, Icon
from src.echo_score import DEFAULT_TEMPLATE, template_names

version = "dev"


def _find_recent_game_launcher():
    try:
        import codecs
        import struct
        import winreg
    except ImportError:
        return None
    root_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
    candidates = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root_key) as root:
            for index in range(winreg.QueryInfoKey(root)[0]):
                guid = winreg.EnumKey(root, index)
                try:
                    with winreg.OpenKey(root, fr"{guid}\Count") as count_key:
                        for value_index in range(winreg.QueryInfoKey(count_key)[1]):
                            encoded, data, _ = winreg.EnumValue(count_key, value_index)
                            path = os.path.expandvars(codecs.decode(encoded, "rot_13"))
                            if path.casefold().endswith(r"\wuthering waves.exe") and Path(path).is_file():
                                last_run = struct.unpack_from("<Q", data, 60)[0] if len(data) >= 68 else 0
                                candidates.append((last_run, path))
                except OSError:
                    continue
    except OSError:
        return None
    return max(candidates, default=(0, None))[1]


def calculate_pc_exe_path(running_path):
    if running_path is None:
        return _find_recent_game_launcher()
    game_folder = Path(running_path).parents[3]
    return str(game_folder / "Wuthering Waves.exe")


def validate_echo_score(key, value):
    from src.globals import Globals
    Globals.apply_echo_score_setting_change(key, value)
    return True, None


echo_score_config = ConfigOption(
    "声骸评分",
    {
        "启用声骸评分": True,
        "角色评分模板": DEFAULT_TEMPLATE,
        "显示主副词条框体": True,
        "Show Debug Boxes": False,
    },
    description="实时识别单个声骸并按角色模板评分",
    config_description={
        "启用声骸评分": "启用后台识别、ECHO-ON 和实时评分",
        "角色评分模板": "输入角色名搜索 XW-UID 角色/流派评分模板",
        "显示主副词条框体": "仅在查看或调谐单个声骸时显示识别框和评分",
        "Show Debug Boxes": "显示 OK Script 的 OCR 调试框",
    },
    config_type={"角色评分模板": {"type": "drop_down", "options": template_names()}},
    validator=validate_echo_score,
    show_at_tab=True,
    icon=Icon.SYNC,
)


config = {
    "debug": False,
    "gui": {"type": "qt"},
    "config_folder": "configs",
    "gui_icon": "icons/icon.png",
    "global_configs": [echo_score_config],
    "ocr": {
        "lib": "onnxocr",
        "auto_simplify": True,
        "params": {"use_openvino": True, "use_npu": True},
    },
    "my_app": ["src.globals", "Globals"],
    "start_timeout": 120,
    "wait_until_settle_time": 0,
    "windows": {
        "top_hwnd_class": [
            re.compile("CAgreementDlg"), re.compile("CLoginDlg_P_"),
            "CefBrowserWindow", "Chrome_RenderWidgetHostHWND", "#32770",
            re.compile("CNativeLoginDlg"), "Static", "ComboBox", "ComboLBox", "Button",
        ],
        "calculate_pc_exe_path": calculate_pc_exe_path,
        "exe": "Client-Win64-Shipping.exe",
        "hwnd_class": "UnrealWindow",
        "interaction": "PostMessage",
        "capture_method": ["WGC", "BitBlt_RenderFull"],
        "check_hdr": False,
        "force_no_hdr": False,
        "check_night_light": True,
        "force_no_night_light": False,
    },
    "window_size": {"width": 1100, "height": 720, "min_width": 1000, "min_height": 680},
    "supported_resolution": {
        "ratio": "16:9",
        "resize_to": [(2560, 1440), (1920, 1080), (1600, 900), (1280, 720)],
        "min_size": (1280, 720),
    },
    "links": {
        "default": {
            "github": "https://github.com/IceHe/ok-wuthering-waves",
            "download": "https://github.com/IceHe/ok-wuthering-waves/releases",
        },
    },
    "about": """
        <p><strong>声骸评分</strong> 基于 OK Script 与 OKWW 的窗口捕获和 OCR 能力。</p>
        <p>本程序只读取游戏窗口画面，不读取内存、不修改游戏文件。</p>
        <p style="color:red;">使用外部辅助工具存在账号风险，请自行判断并承担风险。</p>
    """,
    "screenshots_folder": "screenshots",
    "gui_title": "声骸评分",
    "log_file": "logs/echo-score.log",
    "error_log_file": "logs/echo-score-error.log",
    "launcher_log_file": "logs/launcher.log",
    "launcher_error_log_file": "logs/launcher-error.log",
    "version": version,
    "onetime_tasks": [],
    "trigger_tasks": [["src.task.EchoStatOverlayTask", "EchoStatOverlayTask"]],
}
