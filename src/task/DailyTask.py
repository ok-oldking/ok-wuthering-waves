import re

from ok import Logger
from src.task.BaseWWTask import number_re
from src.task.TacetTask import TacetTask

logger = Logger.get_logger(__name__)


class DailyTask(TacetTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"
        self.name = "Daily Task"

    def run(self):
        self.ensure_main(time_out=120)
        self.farm_tacet()
        self.claim_daily()
        self.claim_mail()
        self.log_info('Task completed')

    def claim_daily(self):
        self.info_set('current task', 'claim daily')
        self.openF2Book()
        self.click(0.04, 0.15, after_sleep=1.5)
        while True:
            boxes = self.ocr(0.23, 0.16, 0.31, 0.69, match=re.compile(r"^[1-9]\d*/\d+$"))
            count = len(boxes)
            self.log_info(f'can claim count {count}')
            if count == 0:
                break
            for _ in range(count):
                self.click(0.87, 0.17, after_sleep=0.5)

        total_points = int(self.ocr(0.19, 0.8, 0.26, 0.88, match=number_re)[0].name)
        self.info_set('daily points', total_points)
        if total_points < 100:
            raise Exception("Can't complete daily task, may need to increase stamina manually!")

        self.click(0.89, 0.85, after_sleep=1)
        self.ensure_main(time_out=5)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.back(after_sleep=1.5)
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=5)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
