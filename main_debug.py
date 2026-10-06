import os

os.environ["PYAPPIFY_PYTHON_TEST"] = "1"
if __name__ == '__main__':
    from src.startup import close_system_informer

    close_system_informer()

    from config import config
    from ok import OK

    config = config
    config['debug'] = True
    # config['click_screenshots_folder'] = "click_screenshots"  # debug用 点击后截图文件夹]
    ok = OK(config)
    ok.start()
