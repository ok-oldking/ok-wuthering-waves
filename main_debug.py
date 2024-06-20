from config import config
from ok.OK import OK

config = config
config['debug'] = True
# config['click_screenshots_folder'] = "click_screenshots"  # debug用 点击后截图文件夹]
ok = OK(config)
ok.start()
