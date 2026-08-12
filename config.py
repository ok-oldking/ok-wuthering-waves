import os
import re
from pathlib import Path

from ok import Box, ConfigOption, Icon
from src.task.process_feature import process_feature

version = "dev"


def _find_most_recently_run_pc_exe():
    try:
        import codecs
        import struct
        import winreg
    except ImportError:
        return None

    user_assist_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
    candidates = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, user_assist_key) as root:
            for index in range(winreg.QueryInfoKey(root)[0]):
                guid = winreg.EnumKey(root, index)
                try:
                    with winreg.OpenKey(root, fr"{guid}\Count") as count_key:
                        for value_index in range(winreg.QueryInfoKey(count_key)[1]):
                            encoded_path, data, _ = winreg.EnumValue(count_key, value_index)
                            path = os.path.expandvars(codecs.decode(encoded_path, "rot_13"))
                            if not path.casefold().endswith(r"\wuthering waves.exe"):
                                continue
                            if not Path(path).is_file():
                                continue
                            last_run = struct.unpack_from("<Q", data, 60)[0] if len(data) >= 68 else 0
                            candidates.append((last_run, path))
                except OSError:
                    continue
    except OSError:
        return None

    return max(candidates, default=(0, None))[1]


def _find_pc_exe_from_registry():
    try:
        import winreg
    except ImportError:
        return None

    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    registry_views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in registry_views:
            try:
                with winreg.OpenKey(root, uninstall_key, 0, winreg.KEY_READ | view) as key:
                    subkey_count = winreg.QueryInfoKey(key)[0]
                    for index in range(subkey_count):
                        try:
                            subkey_name = winreg.EnumKey(key, index)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                display_name = _read_registry_value(subkey, "DisplayName", winreg)
                                if not _is_wuthering_waves_registry_entry(subkey_name, display_name):
                                    continue
                                for value_name in (
                                        "InstallPath", "InstallLocation", "LauncherPath",
                                        "DisplayIcon", "UninstallString"):
                                    registered_path = _read_registry_value(subkey, value_name, winreg)
                                    if game_exe := _find_pc_exe_near_registered_path(registered_path):
                                        return game_exe
                        except OSError:
                            continue
            except OSError:
                continue
    return None


def _read_registry_value(key, name, winreg):
    try:
        return str(winreg.QueryValueEx(key, name)[0])
    except OSError:
        return ""


def _is_wuthering_waves_registry_entry(subkey_name, display_name):
    names = f"{subkey_name} {display_name}".casefold()
    return "wuthering waves" in names or "鸣潮" in names or "鳴潮" in names


def _find_pc_exe_near_registered_path(registered_path):
    if not registered_path:
        return None

    path_text = os.path.expandvars(registered_path.strip().strip('"'))
    exe_end = path_text.casefold().find(".exe")
    if exe_end >= 0:
        path_text = path_text[:exe_end + 4]

    registered = Path(path_text)
    install_folder = registered.parent if registered.suffix.casefold() == ".exe" else registered
    candidates = (
        install_folder / "Wuthering Waves.exe",
        install_folder / "Wuthering Waves Game" / "Wuthering Waves.exe",
        install_folder.parent / "Wuthering Waves Game" / "Wuthering Waves.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def calculate_pc_exe_path(running_path):
    if running_path is None:
        return _find_most_recently_run_pc_exe() or _find_pc_exe_from_registry()
    game_exe_folder = Path(running_path).parents[3]
    return str(game_exe_folder / "Wuthering Waves.exe")


def blur_area(width, height):
    blur_width = int(0.12 * width)
    blur_height = int(0.024 * height)
    return Box(width * 0.879, height * 0.976, blur_width * 0.973, blur_height * 0.994)


key_config_option = ConfigOption('Game Hotkey', {
    'Echo Key': 'q',
    'Liberation Key': 'r',
    'Resonance Key': 'e',
    'Tool Key': 't',
    'Jump Key': 'space',
    'Dodge Key': 'lshift',
    'Wheel Key': 'tab',
    'Guidebook Key': 'f2',
    'Bag Key': 'b',
}, description='In Game Hotkey for Skills', config_description={
    'Bag Key': 'In-game hotkey used to open the Bag.',
}, show_at_tab=True, icon=Icon.GAME)

char_config_option = ConfigOption('Character Config', {
    'Iuno C6': False,
    'Chisa DPS': False,
}, description='Character Config', show_at_tab=True, icon=Icon.PEOPLE)

monthly_card_config_option = ConfigOption('Monthly Card Config', {
    'Check Monthly Card': True,
    'Monthly Card Time': 4
}, description='Turn on to avoid interruption by monthly card when executing tasks', config_description={
    'Check Monthly Card': 'Check for monthly card to avoid interruption of tasks',
    'Monthly Card Time': 'Your computer\'s local time when the monthly card will popup, hour in (1-24)'
})

config = {
    'debug': False,  # Optional, default: False
    'custom_tasks': True,
    'use_gui': True,
    'config_folder': 'configs',
    'blur_area': blur_area,
    'gui_icon': 'icons/icon.png',
    'global_configs': [key_config_option, char_config_option, monthly_card_config_option],
    'custom_tabs': [["src.gui.CharacterCodeTab", "CharacterCodeTab"]],
    'ocr': {
        'lib': 'onnxocr',
        'auto_simplify': True,
        'params': {
            'use_openvino': True,
            'use_npu': True,
        }
    },
    'my_app': ['src.globals', 'Globals'],
    'start_timeout': 120,  # default 60
    'wait_until_settle_time': 0,
    # required if using feature detection
    'template_matching': {
        'coco_feature_json': os.path.join('assets', 'coco_annotations.json'),
        'default_horizontal_variance': 0.002,
        'default_vertical_variance': 0.002,
        'default_threshold': 0.8,
        'feature_processor': process_feature,
        'vcenter_features': ['monthly_card', 'skip_dialog_check'],
        'hcenter_features': ['monthly_card', 'suisui_forte3', 'message_dialog', 'claim_stamina_sign',
                             'skip_dialog_check', 'login_close', 'garden_confirm', 'garden_continue_game',
                             'garden_unpause', 'garden_get_gold', 'garden_get_purple', 'garden_get_skip',
                             'garden_not_interested_confirm', 'garden_not_interested', 'a_garden_back',
                             'garden_get_confirm_gray', 'the_garden_max', 'garden_shop_close', 'garden_new_stage',
                             'a_garden_restart', 'suisui_forte2', 'suisui_e1', 'e_forte', 'f_break_full']
    },
    'windows': {  # required  when supporting windows game
        'top_hwnd_class': [re.compile('CAgreementDlg'), re.compile('CLoginDlg_P_'),
                           'CefBrowserWindow', 'Chrome_RenderWidgetHostHWND', '#32770',
                           re.compile('CNativeLoginDlg'), 'Static', 'ComboBox', 'ComboLBox', 'Button'
                           ],
        'calculate_pc_exe_path': calculate_pc_exe_path,
        'exe': 'Client-Win64-Shipping.exe',
        'hwnd_class': 'UnrealWindow',
        'interaction': 'PostMessage',
        'capture_method': ['WGC', 'BitBlt_RenderFull'],  # Windows版本支持的话, 优先使用WGC, 否则使用BitBlt_Full
        'check_hdr': False,
        'force_no_hdr': False,
        'check_night_light': True,
        'force_no_night_light': False,
    },
    'window_size': {
        'width': 1200,
        'height': 800,
        'min_width': 1200,
        'min_height': 800,
    },
    'supported_resolution': {
        'ratio': '16:9',
        'resize_to': [(2560, 1440), (1920, 1080), (1600, 900), (1280, 720)],
        'min_size': (1280, 720)
    },
    'links': {
        'default': {
            'github': 'https://github.com/ok-oldking/ok-wuthering-waves',
            'discord': 'https://discord.gg/vVyCatEBgA',
            'sponsor': 'https://patreon.com/ok_oldking',
            'share': 'Download OK-WW from https://ok-script.com/ok-ww',
            'faq': 'https://ok-script.com/ok-ww/'
        },
        'zh_CN': {
            'github': 'https://github.com/ok-oldking/ok-wuthering-waves',
            'discord': 'https://discord.gg/vVyCatEBgA',
            'sponsor': 'https://afdian.com/a/ok-oldking',
            'share': '下载okww https://ok-script.com/ok-ww',
            'faq': 'https://ok-script.com/ok-ww',
            'qq_group': 'https://qm.qq.com/q/SUQpIpmq4',
            'qq_channel': 'https://pd.qq.com/s/djmm6l44y',
        },
    },
    'about': """
    <p style="color:red;">
    <strong>本软件是免费开源的。</strong> 如果你被收费，请立即退款。请访问QQ频道或GitHub下载最新的官方版本。
    </p>
    <p style="color:red;">
        <strong>本软件仅供个人使用，用于学习Python编程、计算机视觉、UI自动化等。</strong> 请勿将其用于任何营利性或商业用途。
    </p>
    <p style="color:red;">
        <strong>使用本软件可能会导致账号被封。</strong> 请在了解风险后再使用。
    </p>
""",
    'screenshots_folder': "screenshots",
    'gui_title': 'OK-WW',  # Optional
    # 'coco_feature_folder': get_path(__file__, 'assets/coco_feature'),  # required if using feature detection
    'log_file': 'logs/ok-ww.log',  # Optional, auto rotating every day
    'error_log_file': 'logs/ok-ww_error.log',
    'launcher_log_file': 'logs/launcher.log',
    'launcher_error_log_file': 'logs/launcher_error.log',
    'version': version,
    'onetime_tasks': [  # tasks to execute
        ["src.task.DailyTask", "DailyTask"],
        ["src.task.FarmEchoTask", "FarmEchoTask"],
        ["src.task.NightmareNestTask", "NightmareNestTask"],
        ["src.task.TacetTask", "TacetTask"],
        ["src.task.ForgeryTask", "ForgeryTask"],
        ["src.task.SimulationTask", "SimulationTask"],
        ["src.task.MultiAccountDailyTask", "MultiAccountDailyTask"],
        ["src.task.MergeEchoTask", "MergeEchoTask"],
        ["src.task.EnhanceEchoTask", "EnhanceEchoTask"],
        ["src.task.ChangeEchoTask", "ChangeEchoTask"],
        ["src.task.GardenTask", "GardenTask"],
        # ["src.task.DiagnosisTask", "DiagnosisTask"],
    ], 'trigger_tasks': [
        ["src.task.AutoCombatTask", "AutoCombatTask"],
        ["src.task.AutoPickTask", "AutoPickTask"],
        ["src.task.AutoLoginTask", "AutoLoginTask"],
        ["src.task.SkipDialogTask", "AutoDialogTask"],
        ["src.task.FastTravelTask", "FastTravelTask"],
        ["src.task.MouseResetTask", "MouseResetTask"],
    ], 'scene': ["src.scene.WWScene", "WWScene"],
    'update_pyappify': {
        'to_version': '1.1.9',
        'zip_url': 'https://github.com/ok-oldking/ok-wuthering-waves/releases/download/v3.5.17/ok-ww-win32.zip',
        'sha256': '0ad4d89aae5995641136eb977536a05d2f9c567c9a43ab16c670a947bc301531',
    }

}
