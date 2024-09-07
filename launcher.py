from config import config
from ok.gui.launcher.Launcher import Launcher
from ok.logging.Logger import config_logger

config_logger(config)
Launcher(config).start()
