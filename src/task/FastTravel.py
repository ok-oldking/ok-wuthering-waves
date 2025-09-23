import re
from ok import TriggerTask, Logger


logger = Logger.get_logger(__name__)


class FastTravel(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        # self.trigger_interval = 0.5
        self.name = "Fast Travel"

    def run(self):
        # Fast Travel box position 1480,980, 230, 63 with 1920x1080
        self.log_debug("start run FastTravel.run")
        results = self.ocr(
            box=self.box_of_screen(0.77, 0.90, 0.88, 0.958, hcenter=True),
            # @TODO add more i18n support
            match=re.compile(r'FastTravel|快速旅行'),
            # log=True,
            threshold=0.8)
    
        if results:
            self.log_debug("has result")
            self.click_box(results[0])
            return True
            
