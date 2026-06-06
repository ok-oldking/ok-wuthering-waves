from qfluentwidgets import FluentIcon

from ok import TriggerTask


class CustomAxisRetryTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Custom Axis Retry Until Success"
        self.description = "When enabled, failed custom-axis actions retry every 0.05 seconds and block the next action until success."
        self.icon = FluentIcon.SYNC
        self.trigger_interval = 1
        self.default_config = {
            '_enabled': False,
        }

    def run(self):
        return False
