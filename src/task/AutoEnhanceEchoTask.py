from qfluentwidgets import FluentIcon
from skimage.filters.rank import threshold

from ok import FindFeature, Logger
from ok import TriggerTask
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


class AutoEnhanceEchoTask(TriggerTask, BaseWWTask, FindFeature):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Enhance Echo"
        self.description = "Auto Enhance and Tune Echo after you add EXP Material"
        self.icon = FluentIcon.SHOPPING_CART
        self.scene: WWScene | None = None
        self.default_config.update({
            '_enabled': False,
        })

    def find_echo_enhance(self):
        return self.find_one('echo_enhance_btn')

    def run(self):
        if self.scene.in_team(self.in_team_and_world):
            return
        if enhance_button := self.scene.echo_enhance_btn(self.find_echo_enhance):
            wait = False
            while self.find_one('echo_enhance_to', horizontal_variance=0.01):
                self.click(enhance_button, after_sleep=0.5)
                wait = True
            if wait:
                handled = self.wait_until(lambda: self.do_handle_pop_up(1), time_out=6)
                if handled == 'exit':
                    return True

            if feature := self.wait_feature('red_dot', time_out=3) if wait else self.find_one('red_dot'):
                self.log_info(f'found red dot feature: {feature}')
                self.click(0.04, 0.29, after_sleep=0.5)
                if enhance_button := self.find_echo_enhance():
                    self.click(enhance_button, after_sleep=1)
                    self.wait_until(lambda: self.do_handle_pop_up(2), time_out=6)
            return True

    def do_handle_pop_up(self, step):
        if btn := self.find_one('echo_enhance_confirm'):
            self.click(btn, after_sleep=1)
        elif feature := self.find_one(['echo_enhance_btn', 'red_dot']):
            self.log_info(f'found do_handle_pop_up: {feature}')
            return 'ok'
        elif self.find_one('echo_merge'):
            return 'exit'
        elif step == 1:
            self.click(0.51, 0.87, after_sleep=0.5)
        else:
            self.click(0.04, 0.16, after_sleep=0.5)
