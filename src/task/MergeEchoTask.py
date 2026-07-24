import re

from qfluentwidgets import FluentIcon

from src.task.BaseWWTask import BaseWWTask

FULL_BATCH_PATTERN = re.compile(r"100\s*/\s*100")


class MergeEchoTask(BaseWWTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Merge Discarded Echoes"
        self.description = (
            "Must have 1000 discarded Echo to Run, "
            "Merge discarded Echoes in full batches of 100."
        )
        self.icon = FluentIcon.SYNC
        self.group_name = "Echo"
        self.group_icon = FluentIcon.SYNC

    def run(self):
        self.ensure_main()
        hotkey = self.key_config.get("Bag Key", "b")
        self.send_key(hotkey)
        if not self.wait_until(
            lambda: not self.in_team_and_world(),
            time_out=5,
            raise_if_not_found=False,
        ):
            self.log_error(
                f"can not open bag with hotkey {hotkey}",
                notify=True,
            )
            return
        self.sleep(1)

        if self.wait_click_skip_dialog_confirm():
            self.sleep(2)
        else:
            self.log_error(
                "Must have 1000 discarded Echo to Run",
                notify=True,
            )
            self.ensure_main()
            return

        self.merge_echoes()

    def merge_echoes(self):
        self.open_merge_page()
        while self.merge_full_batch():
            pass

        self.ensure_main()

    def open_merge_page(self):
        self.click_relative(0.602, 0.124, after_sleep=0.5)
        self.click_relative(0.520, 0.904, after_sleep=2)
        self.click_relative(0.041, 0.918, after_sleep=1)
        self.click_relative(0.826, 0.840, after_sleep=0.5)
        self.click_relative(0.717, 0.204, after_sleep=0.5)
        self.click_relative(0.041, 0.918, after_sleep=0.5)

    def merge_full_batch(self):
        self.click_relative(0.310, 0.915, after_sleep=0.5)
        full_batch = self.ocr(
            0.670,
            0.660,
            0.895,
            0.958,
            match=FULL_BATCH_PATTERN,
        )
        if not full_batch:
            self.log_info("All full batches of discarded Echoes have been merged.")
            return False

        self.click_relative(0.782, 0.910)
        self.wait_click_skip_dialog_confirm()
        self.sleep(3)
        self.click_relative(0.496, 0.972, after_sleep=1)
        return True
