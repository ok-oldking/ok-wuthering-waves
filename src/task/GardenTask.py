import re


from ok import Logger, run_task
from config import config
from src.Labels import Labels
from src.task.BaseWWTask import BaseWWTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class GardenTask(WWOneTimeTask, BaseWWTask):
    GARDEN_TARGET_POINTS = re.compile('6000')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "🎡 自动周常乐园"
        self.description = "Detect and click garden actions until the task is stopped."
        self.garden_features = [
            label.value for label in Labels
            if label.value.startswith("garden_")
        ]
        self.garden_priority_features = [
            "garden_get_skip",
            "garden_not_interested_confirm",
        ]

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main()
        self.open_garden_weekly_page()
        if self.is_weekly_garden_completed():
            self.log_info('乐园任务完成, 已达到上限', notify=True)
            return
        self.click(0.246, 0.486, after_sleep=1)
        while True:
            self.sleep(0.1)
            target = self.find_best_garden_feature()
            self.sleep(0.2)
            if target:
                self.info_set("current task", target.name)
                if target.name == 'garden_get_skip':
                    self.sleep(1)
                    self.log_info(f"click garden_get_confirm")
                    if gold := self.find_one('garden_get_gold', horizontal_variance=0.9):
                        self.click(gold, after_sleep=1)
                    elif purple := self.find_one('garden_get_purple', horizontal_variance=0.9):
                        self.click(purple, after_sleep=1)
                    else:
                        self.click(0.5, 0.2, after_sleep=1)
                    self._click_echo_confirm()
                    continue
                elif target.name == 'garden_not_interested':
                    not_interested = self.find_feature('garden_not_interested', vertical_variance=0.4)
                    self.click(not_interested[-1], after_sleep=1)
                    self.click(self.get_box_by_name('garden_not_interested_confirm'), after_sleep=1)
                    continue
                elif target.name == 'garden_start_game':
                    # At Garden Entrance, choose blessing1
                    self._choose_first_blessing()
                self.log_info(f"click {target.name} {target.confidence:.3f}")
                self.click(target, after_sleep=1)
            else:
                garden_restart = self.find_one('a_garden_restart')
                garden_back = self.find_one('a_garden_back')
                if garden_restart and garden_back:
                    # 避免因点击太快，导致[挑战失败]页面中点击[返回主页]失败
                    self.sleep(2)
                    texts = self.ocr(0.373, 0.346, 0.859, 0.615)
                    self.log_info('garden end {}'.format(texts))
                    if self.is_garden_done(texts):
                        self.click(garden_back, after_sleep=1)
                        if self.wait_feature('garden_start_game', settle_time=1, time_out=5):
                            self.back(after_sleep=1)
                        if self.wait_book('gray_book_quest', time_out=30):
                            self.click(0.927, 0.893, after_sleep=2)
                            self.click(0.927, 0.893, after_sleep=1)
                        break
                    else:
                        self.click(garden_restart, after_sleep=1)
                self.sleep(0.2)
        self.log_info('乐园任务完成, 已达到上限', notify=True)

    def open_garden_weekly_page(self):
        self.openF2Book('gray_book_quest')
        self.sleep(1)
        self.click(0.343, 0.129, after_sleep=1)
        self.click(0.927, 0.893, after_sleep=3)
        self.click(0.927, 0.893, after_sleep=2)

    def is_weekly_garden_completed(self):
        current = self.ocr(0.102, 0.793, 0.284, 0.956, match=self.GARDEN_TARGET_POINTS)
        self.log_info(f"Garden current: {current}")
        return bool(current)

    def is_garden_done(self, texts):
        text = " ".join(str(getattr(box, "name", box)) for box in texts)
        return text.count(self.GARDEN_TARGET_POINTS.pattern) != 1

    def find_best_garden_feature(self):
        matches = []
        for feature_name in self.garden_features:
            if not self.feature_exists(feature_name):
                continue
            if feature_name == 'garden_get_confirm_gray' or feature_name == 'garden_not_interested_confirm':
                continue
            if feature_name == 'garden_not_interested':
                matches.extend(self.find_feature(feature_name, vertical_variance=0.4))
            else:
                matches.extend(self.find_feature(feature_name))
        for priority_feature in self.garden_priority_features:
            priority_matches = [
                match for match in matches
                if match.name == priority_feature
            ]
            if priority_matches:
                return max(priority_matches, key=lambda box: box.confidence)
        return max(matches, key=lambda box: box.confidence, default=None)

    def _click_echo_confirm(self):
        """点「声骸选择」页的确认按钮。

        旧实现直接按标注坐标点 garden_get_confirm_gray，并不要求当帧匹配成功。
        选完声骸后按钮常变成高亮态，或者新版本把按钮挪了位置，模板失配时仍然
        按旧坐标点下去，于是出现「选了声骸但确认没生效」，随后代码去点 next_day，
        整个周常就卡在声骸面板上（#1793）。

        这里按层次兜底：先给灰色模板 3 秒（等按钮动画），找不到就 OCR 右下角
        找「确认」，两者都没有才回落到旧坐标。模板能匹配时行为与原来完全一致。
        """
        for _ in range(6):
            box = self.find_one('garden_get_confirm_gray', horizontal_variance=0.9)
            if box:
                self.click(box, after_sleep=1)
                return
            self.sleep(0.5)
        for box in self.ocr(0.45, 0.55, 1.0, 0.98):
            text = str(getattr(box, 'name', box))
            if '确认' in text or '確定' in text or 'Confirm' in text:
                self.click(box, after_sleep=1)
                return
        fallback = self.get_box_by_name('garden_get_confirm_gray')
        if not fallback:
            self.log_info('echo confirm button not found')
            return
        self.log_info(self.tr('click garden_get_confirm'))
        self.click(fallback, after_sleep=1)

    def _choose_first_blessing(self):
        """At Garden Entrance, choose first blessing"""
        # click blessing botton
        self.click(965 / 1920, 860 / 1080, after_sleep=2)
        # choose blessing1(Add-on)
        self.click(700 / 1920, 666 / 1080, after_sleep=2)
        # confirm
        self.click(1600 / 1920, 900 / 1080, after_sleep=2)


if __name__ == "__main__":
    run_task(config, task=GardenTask, debug=True)
