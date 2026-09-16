import re

import cv2

from ok import Logger, run_task
from config import config
from src.Labels import Labels
from src.task.BaseWWTask import BaseWWTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)

# 声骸选择界面文字(底部按钮)
ECHO_CONFIRM_TEXT = re.compile('確認|确认|Confirm', re.IGNORECASE)
ECHO_REFRESH_TEXT = re.compile('刷新|Refresh', re.IGNORECASE)

# 品质优先级: 金 > 紫 > 蓝 > 灰
ECHO_QUALITY_PRIORITY = ('gold', 'purple', 'blue', 'gray')

# 卡片标题栏区域与卡片点击位置 (1920x1080 归一化坐标)
ECHO_CARDS = (
    {'header': (0.167, 0.155, 0.365, 0.210), 'click': (0.263, 0.407)},
    {'header': (0.411, 0.155, 0.609, 0.210), 'click': (0.508, 0.407)},
    {'header': (0.651, 0.155, 0.812, 0.210), 'click': (0.747, 0.407)},
)


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
            if self.handle_garden_echo_select():
                continue
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
                    self.click(self.get_box_by_name('garden_get_confirm_gray'), after_sleep=1)
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

    def handle_garden_echo_select(self):
        """声骸选择界面: 右上角有推荐标识选推荐, 否则按品质优先级 金>紫>蓝>灰 选择"""
        bottom = self.box_of_screen(0.05, 0.70, 0.95, 0.90)
        texts = self.ocr(box=bottom, log=self.debug)
        if not texts:
            return False
        confirm = self.find_boxes(texts, boundary=bottom, match=ECHO_CONFIRM_TEXT)
        refresh = self.find_boxes(texts, boundary=bottom, match=ECHO_REFRESH_TEXT)
        if not (confirm and refresh):
            return False
        self.log_info('garden echo select screen')
        cards = self.scan_garden_echo_cards()
        if not cards:
            return False
        card = self.pick_recommend_card(cards)
        if card is None:
            card = self.pick_quality_card(cards)
        self.log_info(f"choose echo card {card['index']} quality={card['quality']}")
        x, y = card['click']
        self.click(x, y, after_sleep=1)
        self.click(confirm[0], after_sleep=2)
        return True

    def pick_recommend_card(self, cards):
        """右上角有推荐标识(橙色点赞)则选该卡片"""
        box = self.box_of_screen(0.14, 0.10, 0.88, 0.23)
        badge = self.find_one('garden_echo_recommend', box=box, threshold=0.7)
        if not badge:
            return None
        bx = badge.center()[0] / self.width
        self.log_info(f'found recommend badge at {bx:.3f}')
        return min(cards, key=lambda c: abs(c['click'][0] - bx))

    def pick_quality_card(self, cards):
        """按品质优先级 金>紫>蓝>灰 选择"""
        def card_key(c):
            qi = ECHO_QUALITY_PRIORITY.index(c['quality']) \
                if c['quality'] in ECHO_QUALITY_PRIORITY else len(ECHO_QUALITY_PRIORITY)
            return qi
        return min(cards, key=card_key)

    def scan_garden_echo_cards(self):
        """扫描三张声骸卡片标题栏颜色, 判断品质"""
        cards = []
        for i, c in enumerate(ECHO_CARDS):
            quality = self.classify_echo_quality(c['header'])
            if quality:
                cards.append({'index': i + 1, 'quality': quality, 'click': c['click']})
        return cards

    def classify_echo_quality(self, header):
        """按标题栏 HSV 均值判断品质: 灰/蓝/紫/金"""
        box = self.box_of_screen(*header)
        mat = self.frame[box.y:box.y + box.height, box.x:box.x + box.width]
        if mat.size == 0:
            return None
        h, s, v = cv2.split(cv2.cvtColor(mat, cv2.COLOR_BGR2HSV))
        hm, sm, vm = h.mean(), s.mean(), v.mean()
        self.log_debug(f'echo card header HSV=({hm:.0f},{sm:.0f},{vm:.0f})')
        if vm < 150:
            return None
        if 90 <= hm <= 125 and sm >= 40:
            return 'blue'
        if 126 <= hm <= 160 and sm >= 40:
            return 'purple'
        if hm <= 40 and sm >= 90:
            return 'gold'
        return 'gray'

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
