import os
from pathlib import Path

import numpy as np

version = "v5.0.11"


def calculate_pc_exe_path(running_path):
    game_exe_folder = Path(running_path).parents[3]
    return str(game_exe_folder / "Wuthering Waves.exe")


def make_bottom_right_black(frame):
    """
    Changes a portion of the frame's pixels at the bottom right to black.

    Args:
        frame: The input frame (NumPy array) from OpenCV.

    Returns:
        The modified frame with the bottom-right corner blackened.  Returns the original frame
        if there's an error (e.g., invalid frame).
    """
    try:
        height, width = frame.shape[:2]  # Get height and width

        # Calculate the size of the black rectangle
        black_width = int(0.13 * width)
        black_height = int(0.025 * height)

        # Calculate the starting coordinates of the rectangle
        start_x = width - black_width
        start_y = height - black_height

        # Create a black rectangle (NumPy array of zeros)
        black_rect = np.zeros((black_height, black_width, frame.shape[2]), dtype=frame.dtype)  # Ensure same dtype

        # Replace the bottom-right portion of the frame with the black rectangle
        frame[start_y:height, start_x:width] = black_rect

        return frame
    except Exception as e:
        print(f"Error processing frame: {e}")
        return frame


config = {
    'debug': False,  # Optional, default: False
    'use_gui': True,
    'config_folder': 'configs',
    'screenshot_processor': make_bottom_right_black,
    'gui_icon': 'icon.png',
    'ocr': {
        'lib': 'rapidocr_openvino'
    },
    'start_timeout': 120,  # default 60
    'wait_until_settle_time': 0,
    # required if using feature detection
    'template_matching': {
        'coco_feature_json': os.path.join('assets', 'result.json'),
        'default_horizontal_variance': 0.002,
        'default_vertical_variance': 0.002,
        'default_threshold': 0.8,
    },
    'windows': {  # required  when supporting windows game
        'exe': 'Client-Win64-Shipping.exe',
        'calculate_pc_exe_path': calculate_pc_exe_path,
        'hwnd_class': 'UnrealWindow',
        'interaction': 'PostMessage',
        'can_bit_blt': True,  # default false, opengl games does not support bit_blt
        'bit_blt_render_full': True,
        'check_hdr': False,
        'force_no_hdr': False,
        'check_night_light': True,
        'force_no_night_light': False,
        'require_bg': True
    },
    'window_size': {
        'width': 800,
        'height': 600,
        'min_width': 600,
        'min_height': 450,
    },
    'supported_resolution': {
        'ratio': '16:9',
        'min_size': (1280, 720)
    },
    'git_update': {'sources': [{
        'name': 'Global',
        'git_url': 'https://github.com/ok-oldking/ok-ww-update.git',
        'pip_url': 'https://pypi.org/simple/'
    }, {
        'name': '清华大学',
        'git_url': 'https://e.coding.net/g-frfh1513/ok-wuthering-waves/ok-wuthering-waves.git',
        'pip_url': 'https://pypi.tuna.tsinghua.edu.cn/simple'
    }, {
        'name': 'China',
        'git_url': 'https://e.coding.net/g-frfh1513/ok-wuthering-waves/ok-wuthering-waves.git',
        'pip_url': 'https://pypi.tuna.tsinghua.edu.cn/simple'
    }, {
        'name': '腾讯云',
        'git_url': 'https://e.coding.net/g-frfh1513/ok-wuthering-waves/ok-wuthering-waves.git',
        'pip_url': 'https://mirrors.cloud.tencent.com/pypi/simple'
    }, {
        'name': '阿里云',
        'git_url': 'https://e.coding.net/g-frfh1513/ok-wuthering-waves/ok-wuthering-waves.git',
        'pip_url': 'https://mirrors.aliyun.com/pypi/simple'
    },
    ]},
    'links': {
        'default': {
            'github': 'https://github.com/ok-oldking/ok-wuthering-waves',
            'discord': 'https://discord.gg/Sy6etyCRed',
            'share': 'Download OK-WW from https://github.com/ok-oldking/ok-wuthering-waves/releases/latest',
            'faq': 'https://github.com/ok-oldking/ok-wuthering-waves#FAQ'
        },
        'zh_CN': {
            'github': 'https://github.com/ok-oldking/ok-wuthering-waves',
            'discord': 'https://discord.gg/Sy6etyCRed',
            'share': 'OK-WW 夸克网盘下载：https://pan.quark.cn/s/75b55ef72a34 GitHub下载: https://github.com/ok-oldking/ok-wuthering-waves/releases/latest',
            'qq_group': 'https://qm.qq.com/q/ufUCrCEq6A',
            'faq': 'https://gitee.com/ok-olding/ok-wuthering-waves/blob/master/README_cn.md#%E5%87%BA%E7%8E%B0%E9%97%AE%E9%A2%98%E8%AF%B7%E6%A3%80%E6%9F%A5',
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
        ["src.task.TacetTask", "TacetTask"],
        ["src.task.FarmEchoTask", "FarmEchoTask"],
        ["src.task.FarmWorldBossTask", "FarmWorldBossTask"],
        ["src.task.DiagnosisTask", "DiagnosisTask"],
    ], 'trigger_tasks': [
        ["src.task.AutoCombatTask", "AutoCombatTask"],
        ["src.task.AutoPickTask", "AutoPickTask"],
        ["src.task.SkipDialogTask", "AutoDialogTask"],
        ["src.task.MouseResetTask", "MouseResetTask"],
        ["src.task.AutoLoginTask", "AutoLoginTask"],
    ]
}
