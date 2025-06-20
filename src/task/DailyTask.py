import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseWWTask import number_re
from src.task.TacetTask import TacetTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DailyTask(TacetTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"
        self.name = "Daily Task"
        self.add_exit_after_config()
        self.show_create_shortcut = True
        self.icon = FluentIcon.CAR

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=180)
        self.farm_tacet()
        self.sleep(4)
        self.claim_daily()
        self.claim_mail()
        self.claim_millage()
        self.log_info('Task completed', notify=True)

    def claim_millage(self):
        self.log_info('open_millage')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.86, 0.05)
        self.send_key_up('alt')
        self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'), settle_time=1, raise_if_not_found=True, log=True)
        self.click(0.04, 0.3, after_sleep=1)
        self.click(0.68, 0.91, after_sleep=1)
        self.ensure_main()

    def claim_daily(self):
        self.info_set('current task', 'claim daily')
        self.ensure_main(time_out=5)
        self.openF2Book()
        gray_book_quest = self.openF2Book("gray_book_quest")
        self.click_box(gray_book_quest, after_sleep=1.5)
        while True:
            boxes = self.ocr(0.23, 0.16, 0.31, 0.69, match=re.compile(r"^[1-9]\d*/\d+$"))
            count = 0
            for box in boxes:
                parts = box.name.split('/')
                if len(parts) == 2 and parts[0] == parts[1]:
                    count += 1

            self.log_info(f'can claim count {count}')
            if count == 0:
                break
            for _ in range(count):
                self.click(0.87, 0.17, after_sleep=0.5)
            self.sleep(1)

        total_points = int(self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)[0].name)
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
