import os

from ok.util.path import get_path_in_package
from src.task.AutoCombatTask import AutoCombatTask
from src.task.FarmEchoTask import FarmEchoTask
from src.task.FarmWorldBossTask import FarmWorldBossTask
from src.task.SkipDialogTask import AutoDialogTask

version = "v3.0.11"


def calculate_pc_exe_path(running_path):
    return running_path


config = {
    'debug': False,  # Optional, default: False
    'use_gui': True,
    'config_folder': 'configs',
    'gui_icon': get_path_in_package(__file__, 'icon.png'),
    'ocr': {
        'lib': 'RapidOCR'
    },
    # required if using feature detection
    'template_matching': {
        'coco_feature_json': os.path.join('assets', '_annotations.coco.json'),
        'default_horizontal_variance': 0.002,
        'default_vertical_variance': 0.002,
        'default_threshold': 0.9,
    },
    'windows': {  # required  when supporting windows game
        'exe': 'Client-Win64-Shipping.exe',
        'calculate_pc_exe_path': calculate_pc_exe_path,
        'interaction': 'PostMessage',
        'can_bit_blt': True,  # default false, opengl games does not support bit_blt
        'bit_blt_render_full': True,
        'check_hdr_and_night_light': True
    },
    'supported_resolution': {
        'ratio': '16:9',
        'min_size': (1600, 900)
    },
    'analytics': {
        'report_url': 'https://okreport.ok-script.com/report'
    },
    'update': {
        'releases_url': 'https://api.github.com/repos/ok-oldking/ok-wuthering-waves/releases?per_page=15',
        'proxy_url': 'https://gh.ok-script.com/',
        'exe_name': 'ok-ww.exe',
        'use_proxy': True
    },
    'about': """
    <h3>OK-WW</h3>
    <p>GitHub <a href="https://github.com/ok-oldking/ok-wuthering-waves">https://github.com/ok-oldking/ok-wuthering-waves</></p>
    <p>Report a BUG <a href="https://github.com/ok-oldking/ok-wuthering-waves/issues/new?assignees=ok-oldking&labels=bug&projects=&template=%E6%8A%A5%E5%91%8Abug-.md&title=%5BBUG%5D">https://github.com/ok-oldking/ok-wuthering-waves/issues/new?assignees=ok-oldking&labels=bug&projects=&template=%E6%8A%A5%E5%91%8Abug-.md&title=%5BBUG%5D</></p>
    <p>QQ群:<a href="https://qm.qq.com/q/qMezq2IDGU">970523295</a></p>
    <p>QQ频道:<a href="https://pd.qq.com/s/75758wrmp">OK-WW</a></p>
    <p>本软件免费, 如果你被收费请立即退款, 请到QQ频道或者GitHub下载最新官方版</p>
""",
    'supported_screen_ratio': '16:9',
    'screenshots_folder': "screenshots",
    'gui_title': 'OK-WW',  # Optional
    # 'coco_feature_folder': get_path(__file__, 'assets/coco_feature'),  # required if using feature detection
    'log_file': 'logs/ok-script.log',  # Optional, auto rotating every day
    'error_log_file': 'logs/ok-script_error.log',
    'version': version,
    'onetime_tasks': [  # tasks to execute
        FarmEchoTask,
        FarmWorldBossTask
    ], 'trigger_tasks': [
        AutoCombatTask,
        AutoDialogTask
    ]
}
