import os
from pathlib import Path

version = "v5.0.11"


def calculate_pc_exe_path(running_path):
    game_exe_folder = Path(running_path).parents[3]
    return str(game_exe_folder / "Wuthering Waves.exe")


config = {
    'debug': False,  # Optional, default: False
    'use_gui': True,
    'config_folder': 'configs',
    'gui_icon': 'icon.png',
    'ocr': {
        'lib': 'rapidocr_openvino'
    },
    'start_timeout': 120,  # default 60
    'wait_until_before_delay': 2,  # default 1 , for wait_until() function
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
    'analytics': {
        'report_url': 'http://111.231.71.225/report'
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
            'faq': 'https://github.com/ok-oldking/ok-wuthering-waves#FAQ'
        },
        'zh_CN': {
            'github': 'https://github.com/ok-oldking/ok-wuthering-waves',
            'faq': 'https://github.com/ok-oldking/ok-wuthering-waves#FAQ',
        },
    },
    'about': """
    <h3>OK-WW</h3>
    <p>GitHub <a href="https://github.com/ok-oldking/ok-wuthering-waves">https://github.com/ok-oldking/ok-wuthering-waves</></p>
    <p>Report a BUG <a href="https://github.com/ok-oldking/ok-wuthering-waves/issues/new?assignees=ok-oldking&labels=bug&projects=&template=%E6%8A%A5%E5%91%8Abug-.md&title=%5BBUG%5D">https://github.com/ok-oldking/ok-wuthering-waves/issues/new?assignees=ok-oldking&labels=bug&projects=&template=%E6%8A%A5%E5%91%8Abug-.md&title=%5BBUG%5D</></p>
    <p>QQ群:<a href="https://qm.qq.com/q/qMezq2IDGU">970523295</a></p>
    <p>QQ频道:<a href="https://pd.qq.com/s/75758wrmp">OK-WW</a></p>
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
