from qfluentwidgets import FluentIcon

from ok import TriggerTask


class CustomAxisGlobalFTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Custom Axis Global F"
        self.description = "When enabled, every custom-axis action checks the same F interaction logic used by axis F actions before and after the action."
        self.icon = FluentIcon.FLAG
        self.trigger_interval = 1
        self.default_config = {
            '_enabled': False,
        }

    def run(self):
        return False
