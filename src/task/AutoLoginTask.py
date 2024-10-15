from qfluentwidgets import FluentIcon

from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask
from src.task.BaseWWTask import BaseWWTask

logger = get_logger(__name__)


class AutoLoginTask(BaseWWTask, TriggerTask):

    def __init__(self):
        super().__init__()
        self.default_config = {'_enabled': True}
        self.trigger_interval = 5
        self.name = "Auto Login"
        self.description = "Auto Login After Game Starts"
        self.icon = FluentIcon.ACCEPT
        self._logged_in = False

    def trigger(self):
        if self._logged_in:
            pass
        elif self.in_team_and_world():
            self._logged_in = True
        elif self.find_one('login_account', threshold=0.7):
            self.wait_until(lambda: self.find_one('login_account', threshold=0.7) is None,
                            pre_action=lambda: self.click_relative(0.5, 0.9),
                            wait_until_check_delay=3, time_out=30)
            self.wait_until(lambda: self.find_one('monthly_card', threshold=0.7) or self.in_team_and_world(),
                            pre_action=lambda: self.click_relative(0.5, 0.9),
                            wait_until_check_delay=3, time_out=120)
            self.wait_until(lambda: self.in_team_and_world(),
                            post_action=lambda: self.click_relative(0.5, 0.9),
                            wait_until_check_delay=3, time_out=5)
            self.log_info('Auto Login Success', notify=True)
            self._logged_in = True
