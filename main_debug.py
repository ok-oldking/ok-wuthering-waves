import os
import sys

from src.startup import configure_game_bound_overlay, ensure_windows_admin

os.environ["PYAPPIFY_PYTHON_TEST"] = "1"

if __name__ == '__main__':
    if not ensure_windows_admin():
        sys.exit(0)
    configure_game_bound_overlay()

    from config import config
    from ok import OK

    config = config
    config['debug'] = True
    # config['click_screenshots_folder'] = "click_screenshots"  # debug用 点击后截图文件夹]
    ok = OK(config)
    ok.start()
