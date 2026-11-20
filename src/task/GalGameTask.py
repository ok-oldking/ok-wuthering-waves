import re
from collections import deque
from time import monotonic

import cv2
import numpy as np

from ok import BaseTask

from src.task.task_icons import task_icon


DATE = re.compile(r"(0[1-9]|1[0-2])[/／](0[1-9]|[12]\d|3[01])(?:周[一二三四五六日])?")
REWARD_PAGES = ("限时奖励", "常驻奖励")
REWARD_PROGRESS = re.compile(r"(\d+)\s*[/／]\s*(14|15)")
LETTER_PAGE = re.compile(r"[1-9]/[1-9]")
STORY_CHOICES = (
    "之前在列车", "在列车上", "昨天在列车", "昨天在火车", "昨天在电车", "回到原本的世界", "我想回去",
    "是的",
    "休息一下再回去", "同时加入", "在天马集团之前买下", "综合素质", "学业与逻辑", "洛可可帮忙",
    "学生理事会", "回家吧", "开启下一周目", "开启新周目",
)
COURSES = {
    "理科教室": ("课堂助教", "进阶理科课", "理科课程"),
    "文科教室": ("进阶文科课", "文科课程"),
    "操场": ("协助训练", "日常锻炼"),
    "家庭餐厅": ("前台收银", "点单服务"),
    "中央广场": ("校园清洁",),
    "学院商店": ("店员帮忙", "商品销售", "货物整理"),
    "外事联络中心": ("物资采购",),
    "学生理事会": ("学院宣传", "文书处理"),
    "社团联合": ("活动运营", "协助训练"),
    "海滨": ("滨海采风",),
}
OUTINGS = (
    "礼堂", "教学楼", "入学报到", "百年校庆", "期末综合测验", "期末测验", "预选赛", "暑期作战",
    "检定考试", "成人礼庆典", "成人礼", "全国大赛", "最终考察", "毕业典礼",
)
EXAM_ANSWERS = {
    (7, 1): (r"判断.*(?:感受|立场)", r"斜边的平方", r"(?:两者|二者|都).*(?:一样|相同|相等)"),
    (7, 2): (r"弦乐器", r"表达.*(?:情感|思想)", r"(?:舞台|表演).*(?:生动|统一|完整)"),
    (9, 2): (r"^4倍$", r"^25$", r"^28$"),
    (9, 3): (r"竖琴", r"明暗关系", r"低音提琴"),
    (11, 26): (r"入射角", r"一手.*二手|一次资料.*二次资料"),
    (11, 27): (r"音高.*音量|声音的高低.*声音的大小", r"打击乐器"),
}


class GalGameTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "3.8 GalGame"
        self.description = "从「第二索拉：未名之梦」活动页开始，推进学期并领取可用活动奖励。仅支持简体中文。"
        self.group_name = "Daily Activities"
        self.group_icon = task_icon("category-daily")
        self.supported_languages = ["zh_CN"]

    def _read(self):
        self.next_frame()
        return self.ocr(0, 0, 1, .987)

    def _label(self, boxes, label, region=(0, 0, 1, 1), *, contains=False):
        x1, y1, x2, y2 = region
        for box in boxes:
            x, y = box.center()
            text = re.sub(r"\s+", "", box.name)
            if (x1 <= x / self.width <= x2 and y1 <= y / self.height <= y2
                    and (label in text if contains else label == text)):
                return box
        return None

    def _lobby(self, boxes):
        return self._label(boxes, "开始新学期", (.65, .55, .98, .96))

    def _date(self, boxes):
        for box in boxes:
            if box.x < .14 * self.width and box.y < .12 * self.height:
                if match := DATE.fullmatch(box.name.replace(" ", "")):
                    return tuple(map(int, match.groups()))
        return None

    def _resume_state(self, boxes):
        return (
            self._lobby(boxes) or self._settings(boxes) or self._date(boxes) or self._dialogue_panel(boxes)
            or self._confirm_event(boxes) or self._study_focus(boxes) or self._full_choice(boxes)
            or self._label(boxes, "是否快速跳过剧情", (.23, .3, .8, .58), contains=True)
            or self._label(boxes, "好感度提升", (.25, .24, .55, .36), contains=True)
            or self._label(boxes, "新增物品", (.06, .2, .33, .4), contains=True)
            or self._label(boxes, "属性提升", (.35, .26, .65, .39))
            or self._label(boxes, "本月总结", (.16, .03, .42, .14))
            or self._schedule_save(boxes)
            or self._commission_offer(boxes)
            or self._attribute_check(boxes)
            or self._attribute_result(boxes)
            or self._lottery_screen(boxes)
            or self._shop_screen(boxes)
            or self._label(boxes, "「理科课程」", (.2, .34, .8, .59), contains=True)
            or self._forum(boxes)
            or self._paper_choice(boxes)
            or self._label(boxes, "课题清单", (0, 0, .2, .12), contains=True)
            or self._label(boxes, "档案管理", (0, 0, .2, .12), contains=True)
            or any(self._label(boxes, title, (0, 0, .2, .13)) for title in REWARD_PAGES)
            or self._label(boxes, "结束", (.83, .9, .97, .98))
            or self._letter(boxes)
            or self._envelope(boxes)
            or self._black_narration(boxes)
        )

    def _confirm_event(self, boxes):
        prompts = ("是否外出", "选择该方向后", "是否开始执行", "是否开始日程", "是否执行日程",
                   "将结束今日的地图探索")
        if self._starting_semester:
            prompts += ("是否开始新学期", "是否开启新学期")
        if any(self._label(boxes, label, (.2, .34, .8, .59), contains=True) for label in prompts):
            return self._label(boxes, "确认", (.61, .75, .8, .9))
        return None

    def _study_focus(self, boxes):
        if not self._label(boxes, "学业的追求与逻辑的锻炼", (.46, .28, .92, .44), contains=True):
            return None
        focus = self._label(boxes, "综合素质的全面成长与发展", (.46, .68, .92, .84), contains=True)
        locked = self._label(boxes, "后解锁", (.46, .81, .92, .95), contains=True)
        if focus and not locked:
            return focus
        return self._label(boxes, "学业的追求与逻辑的锻炼", (.46, .28, .92, .44), contains=True)

    def _forum(self, boxes):
        return self._label(boxes, "SOLAR-X", (.12, .045, .29, .1), contains=True)

    def _full_choice(self, boxes):
        if (self._label(boxes, "个人背包", (.48, .02, .66, .13), contains=True)
                or self._label(boxes, "阶段目标", (.72, .11, .91, .22), contains=True)):
            return None
        key = self._label(boxes, "F", (.4, .28, .53, .88))
        options = [b for b in boxes if .57 < b.x / self.width < .88
                   and .28 < b.center()[1] / self.height < .9
                   and re.search(r"[\u4e00-\u9fff\d]", b.name)]
        if not options:
            return None
        selected = self._selected_choice(options, key, .422, .45, .052)
        if not selected:
            return None
        if answer := self._exam_answer(options, self._date(boxes)):
            return answer
        for title in ("理事会组织的学院开放日", *STORY_CHOICES):
            if option := self._label(options, title, contains=True):
                _, y = option.center()
                half = round(.009 * self.height)
                fill = self.frame[y - half:y + half, round(.54 * self.width):round(.575 * self.width)]
                if np.mean(fill) > 165:
                    return option
        return selected

    def _letter(self, boxes):
        return any(.47 < b.center()[0] / self.width < .53 and .875 < b.center()[1] / self.height < .93
                   and LETTER_PAGE.fullmatch(b.name) for b in boxes)

    def _envelope(self, boxes):
        return (self._label(boxes, "致:", (.18, .22, .38, .33), contains=True)
                or self._label(boxes, "致：", (.18, .22, .38, .33), contains=True))

    def _black_narration(self, boxes):
        if np.mean(self.frame) >= 25:
            return False
        return any(.15 < b.center()[0] / self.width < .85 and .3 < b.center()[1] / self.height < .7
                   and re.search(r"[\u4e00-\u9fff]", b.name) for b in boxes)

    def _commission_offer(self, boxes):
        if self._label(boxes, "特别委托", (.3, .13, .5, .24)):
            return self._label(boxes, "接取委托", (.5, .85, .8, .97))
        return None

    def _commission_unmet(self, boxes):
        for box in boxes:
            x, y = box.center()
            if .38 < x / self.width < .88 and .45 < y / self.height < .6:
                if match := re.fullmatch(r"(\d+)\s*[/／]\s*(\d+)", box.name.replace(" ", "")):
                    if int(match[1]) < int(match[2]):
                        return True
        return False

    def _attribute_check(self, boxes):
        if not self._label(boxes, "我的属性", (.81, .105, .96, .19), contains=True):
            return None
        options = [b for b in boxes if .14 < b.x / self.width < .435
                   and .62 < b.center()[1] / self.height < .891
                   and re.search(r"[\u4e00-\u9fff]", b.name)]
        for phrase in ("推理", "知识", "思考"):
            if option := self._label(options, phrase, contains=True):
                return option
        key = self._label(boxes, "F", (.126, .61, .195, .9))
        selected = self._selected_choice(options, key, .175, .197, .05)
        return selected or next(iter(options), None)

    def _attribute_result(self, boxes):
        button = self._label(boxes, "完成", (.43, .805, .58, .91))
        if button:
            paper = self.frame[round(.49 * self.height):round(.74 * self.height),
                               round(.38 * self.width):round(.64 * self.width)]
            if np.mean(paper > 180) > .78:
                return button
        return None

    def _lottery_screen(self, boxes):
        return self._label(boxes, "特别刮奖", (.76, .115, .995, .2), contains=True)

    def _shop_screen(self, boxes):
        return (self._label(boxes, "学院商店", (0, 0, .2, .12))
                and self._label(boxes, "商店刷新", (.85, .14, .99, .22), contains=True))

    def _buy_in_shop(self, boxes):
        slots = ((.30, .68), (.30, .40), (.42, .40), (.54, .40), (.66, .40))
        if self._shop_buys < 3:
            self.click(*slots[self._shop_buys % len(slots)], after_sleep=.35)
            updated = self._read()
            if buy := self._label(updated, "购买", (.75, .84, .95, .94)):
                self.click(buy, after_sleep=.7)
                popup = self._read()
                if confirm := (self._label(popup, "确认", (.43, .7, .8, .92))
                               or self._label(popup, "确定", (.32, .69, .72, .96))):
                    self.click(confirm, after_sleep=.6)
                elif (self._label(popup, "获得", (.4, .18, .6, .4))
                      or self._label(popup, "点击空白处继续", (.36, .82, .64, .96))):
                    self.click(.5, .89, after_sleep=.5)
                self._shop_buys += 1
                return
            self._need_shop_buy = False
        self._need_shop_buy = False
        self.click(.954, .067, after_sleep=.65)

    def _play_lottery(self):
        icon = self.frame[round(.044 * self.height):round(.091 * self.height),
                          round(.788 * self.width):round(.833 * self.width)]
        hue, saturation, value = cv2.split(cv2.cvtColor(icon, cv2.COLOR_BGR2HSV))
        colored = (saturation > 115) & (value > 150)
        if np.mean(colored) < .03:
            self.sleep(.5)
            return
        # The balance switches from a red ticket to a gold coin after the last free draw.
        if np.mean(colored & ((hue < 10) | (hue > 170))) < .02:
            self._finished_lottery = True
            self.click(.942, .067, after_sleep=.75)
            return
        digits = self.ocr(.827, .038, .896, .103, match=re.compile(r"^[1-9]\d?$"), target_height=1440)
        if digits:
            index = self._lottery_index % 28
            self._lottery_index += 1
            self.click(.231 + .0683 * (index % 7), .38 + .121 * (index // 7), after_sleep=.85)
        else:
            self.sleep(.5)

    def _paper_choice(self, boxes):
        if (self._label(boxes, "个人背包", (.48, .02, .66, .13), contains=True)
                or self._label(boxes, "阶段目标", (.72, .11, .91, .22), contains=True)):
            return None
        key = self._label(boxes, "F", (.7, .5, .755, .88))
        choices = [b for b in boxes if .28 < b.x / self.width < .67
                   and .53 < b.center()[1] / self.height < .88
                   and re.search(r"[\u4e00-\u9fff\d]", b.name)]
        selected = self._selected_choice(choices, key, .271, .286, .047)
        if selected:
            return self._exam_answer(choices, self._date(boxes)) or selected
        return None

    def _selected_choice(self, options, key, left, right, half_height):
        if key:
            return next((b for b in options
                         if abs(b.center()[1] - key.center()[1]) < .026 * self.height), None)
        if len(options) < 2:
            return None
        x1, x2 = round(left * self.width), round(right * self.width)
        half = round(half_height * self.height)
        for option in options:
            _, y = option.center()
            hsv = cv2.cvtColor(self.frame[y - half:y + half, x1:x2], cv2.COLOR_BGR2HSV)
            gold = (hsv[:, :, 0] > 18) & (hsv[:, :, 0] < 40) & (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 215)
            if np.mean(np.any(gold, axis=1)) > .55:
                return option
        return None

    def _exam_answer(self, options, date):
        for pattern in EXAM_ANSWERS.get(date or self._active_date, ()):
            if answer := next((b for b in options if re.search(pattern, b.name)), None):
                return answer
        return None

    def _dialogue_panel(self, boxes):
        frame = self.frame
        panel = frame[round(.95 * self.height):round(.975 * self.height),
                      round(.755 * self.width):round(.785 * self.width)]
        levels = panel.mean(axis=2)
        return (np.mean(levels > 155) > .70 and np.mean(levels < 90) > .015
                and any(.24 < b.x / self.width < .76 and .85 < b.center()[1] / self.height < .94
                        and re.search(r"[\u4e00-\u9fff]", b.name) for b in boxes))

    def reset_to_start(self):
        # The activity's current journey is the baseline, including in-progress saves.
        self._claim_log = {}
        self._astrite_remaining = {}
        self._need_shop_buy = False
        self._shop_buys = 0
        self._friend_levels = {}
        self._reward_checkpoints = set()
        self._story_ending = False
        self._schedule_tabs = {}
        self._active_date = None
        self._starting_semester = False
        self._finished_lottery = False
        self._lottery_index = 0
        self._skipped_commissions = set()
        self._too_tired_rooms = set()
        self._current_room = None

    def verify_start_state(self):
        return bool(self.wait_until(lambda: self._resume_state(self._read()), time_out=8))

    def _reward_page(self, title):
        return self.ocr(.035, .035, .18, .09, match=title)

    def _settings(self, boxes):
        return self._label(boxes, "设置", (.79, .03, .92, .11)) and self._label(
            boxes, "退出游戏", (.52, .81, .71, .94))

    def _reward_counts(self, boxes):
        for box in boxes:
            if box.x < .15 * self.width and (match := REWARD_PROGRESS.fullmatch(box.name)):
                earned, total = map(int, match.groups())
                self._claim_log[REWARD_PAGES[total - 14]] = f"{earned}/{total}"

    def _all_rewards_earned(self):
        return (len(self._astrite_remaining) == len(REWARD_PAGES)
                and all(count == 0 for count in self._astrite_remaining.values()))

    def _row_has_astrite(self, cy):
        y1 = max(0, round(cy - .045 * self.height))
        y2 = min(self.height, round(cy + .045 * self.height))
        roi = self.frame[y1:y2, round(.655 * self.width):round(.712 * self.width)]
        if roi.size == 0:
            return False
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        astrite = (hsv[:, :, 0] >= 92) & (hsv[:, :, 0] <= 122) & (hsv[:, :, 1] >= 40) & (hsv[:, :, 2] >= 150)
        return float(np.mean(astrite)) > .03

    def _count_astrite_in_progress(self, title, boxes):
        max_y = .80 if title == "限时奖励" else .92
        rows = [b for b in boxes if .80 < b.center()[0] / self.width < .95
                and .15 < b.center()[1] / self.height < max_y and "进行中" in b.name]
        if title == "限时奖励":
            self._need_shop_buy = bool(self._label(boxes, "累计购买商品", (.35, .15, .75, .80), contains=True))
        return sum(1 for row in rows if self._row_has_astrite(row.center()[1]))

    def _claim_rewards(self, title, button):
        opened = False
        for attempt in range(3):
            if attempt > 0:
                boxes = self._read()
                if self._label(boxes, "档案管理", (0, 0, .2, .12), contains=True):
                    self.click(.954, .068, after_sleep=.65)
                    boxes = self._read()
                elif self._tutorial(boxes):
                    boxes = self._read()
                button = self._label(boxes, title, (0, .42, .2, .9)) or button
            self.click(button, after_sleep=.55)
            if self.wait_until(lambda: self._reward_page(title), time_out=2.5):
                opened = True
                break
        if not opened:
            raise RuntimeError(f"无法打开{title}。")

        for _ in range(8):
            boxes = self._read()
            if (self._label(boxes, "获得", (.45, .19, .55, .36)) or
                    self._label(boxes, "点击空白处继续", (.36, .82, .64, .96))):
                self.click(.5, .89, after_sleep=.5)
                continue
            if claim := self._label(boxes, "领取奖励", (.81, .13, .95, .95)):
                self.click(claim, after_sleep=.65)
                continue
            if not self._label(boxes, title, (0, 0, .2, .13)):
                self.sleep(.4)
                continue
            status = self.ocr(.8, .175, .95, .29)
            roi = self.frame[round(.19 * self.height):round(.27 * self.height),
                             round(.84 * self.width):round(.92 * self.width)]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            checked = np.mean((hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 75)
                              & (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 150)) > .015
            if not checked and not any(re.search(r"进行中|已领取|已完成", b.name) for b in status):
                self.sleep(.4)
                continue
            self._astrite_remaining[title] = self._count_astrite_in_progress(title, boxes)
            # Available tasks sort first, and one button claims all on that page.
            self.click(.954, .067, after_sleep=.7)
            return
        raise RuntimeError(f"无法确认{title}的领取状态。")

    def _collect_rewards(self, boxes, parent):
        self._reward_counts(boxes)
        for title in REWARD_PAGES:
            button = self._label(boxes, title, (0, .42, .2, .9))
            if button:
                self._claim_rewards(title, button)
                boxes = None
                for _ in range(3):
                    boxes = self.wait_until(lambda: (frame if parent(frame := self._read())
                                                     else None), time_out=2.5)
                    if boxes:
                        self.sleep(.35)
                        settled = self._read()
                        if parent(settled):
                            boxes = settled
                        break
                    if self._reward_page(title):
                        self.click(.954, .067, after_sleep=.7)
                if not boxes:
                    raise RuntimeError("领取奖励后无法返回活动菜单。")
        if self._claim_log:
            self.info_set("奖励进度", dict(self._claim_log))
        return boxes

    def _dialogue(self, boxes):
        if self._label(boxes, "是否快速跳过剧情", (.23, .3, .8, .58), contains=True):
            if self._label(boxes, "本次登录不再提醒"):
                self.click(.431, .492, after_sleep=.12)
            self.click(.694, .832, after_sleep=.6)
            return True
        if any(self._label(boxes, label, (.83, .9, .97, .98)) for label in ("结束", "下一页")):
            self.click(.894, .872, after_sleep=.6)
            return True
        options = [b for b in boxes if b.x > .67 * self.width
                   and .25 < b.y / self.height < .73 and re.search(r"[\u4e00-\u9fff]", b.name)]
        key = self._label(boxes, "F", (.65, .25, .7, .76))
        panel = self._dialogue_panel(boxes)
        if options and (key or (panel and self.ocr(.78, .05, .83, .11, match="Tab"))):
            if answer := self._exam_answer(options, self._date(boxes)):
                self.click(answer, after_sleep=.65)
                return True
            for phrase in STORY_CHOICES:
                if option := self._label(options, phrase, contains=True):
                    self.click(option, after_sleep=.65)
                    return True
            self.click(options[0], after_sleep=.65)
            return True
        if self._label(boxes, "长按加速", (.83, .88, 1, .98), contains=True):
            self.click(.954, .068, after_sleep=.55)
            return True
        if self._black_narration(boxes):
            self.click(.954, .068, after_sleep=.55)
            return True
        if panel:
            self.click(.77, .955, after_sleep=.45)
            return True
        return False

    def _map_marker(self, boxes):
        # Red exclamation badges are map events. OCR supplies the map context,
        # while the icon remains readable when a building label is obscured.
        frame = self.frame
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hue, saturation, value = cv2.split(hsv)
        mask = ((hue < 8) | (hue > 170)) & (saturation > 145) & (value > 175)
        _, _, stats, centers = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
        directions = ()
        for (x, y, w, h, area), (cx, cy) in zip(stats[1:], centers[1:]):
            rx, ry = cx / self.width, cy / self.height
            if not (.025 < rx < .985 and .07 < ry < .96
                    and .011 < w / self.width < .042 and .018 < h / self.height < .07
                    and .58 < w / h < 1.45 and area > .35 * w * h):
                continue
            red_icon = hsv[y:y + h, x:x + w]
            white = (red_icon[:, :, 1] < 65) & (red_icon[:, :, 2] > 195)
            if np.count_nonzero(white) <= .07 * w * h:
                continue
            for box in boxes:
                tx, ty = box.center()
                if tx / self.width > .71 and ty / self.height < .36:
                    continue
                if any(word in box.name for word in ("阶段目标", "距离", "还有")):
                    continue
                if (0 < cx - tx < .09 * self.width and 0 < ty - cy < .065 * self.height
                        and 2 <= len(box.name) <= 10 and re.search(r"[\u4e00-\u9fff]", box.name)):
                    return box, ()
            if w / self.width >= .018:
                horizontal = "a" if rx < .22 else "d" if rx > .84 else ""
                vertical = "w" if ry < .185 else "s" if ry > .865 else ""
                if horizontal or vertical:
                    directions = tuple(horizontal + vertical)
        return None, directions

    def _enter_location(self, location):
        self.click(location, after_sleep=.75)
        boxes = self._read()
        if self._label(boxes, "个人背包", (.48, .02, .66, .13), contains=True):
            same = self._label(boxes, location.name, (.06, .2, .93, .97))
            if same:
                x, y = same.center()
                self.click(int(x - .02 * self.width), int(y - .11 * self.height), after_sleep=.65)

    def _tutorial(self, boxes):
        if direction := self._label(boxes, "前往【", (.1, .2, .9, .79), contains=True):
            x, y = direction.center()
            self.click(x / self.width, min(.94, y / self.height + .17), after_sleep=.7)
            return True
        for text, point in (
            ("点击【背包】", (.247, .86)),
            ("使用【日常补给】", (.786, .886)),
            ("在当前周目结束后不会消失", (.58, .45)),
            ("剧情选择会影响属性培养方向", (.115, .77)),
            ("此处会显示当前历程的", (.938, .234)),
            ("可以邀请伙伴外出或赠送礼物", (.326, .5)),
            ("可进行【档案存储】", (.954, .067)),
            ("点击【档案存储】", (.382, .808)),
            ("可查看个人信息与角色好感度", (.246, .68)),
            ("角色会发布【限时】任务", (.655, .49)),
            ("需要连续占用多天的日程", (.516, .27)),
            ("执行【休息】类行为后", (.773, .15)),
        ):
            if self._label(boxes, text, contains=True):
                self.click(*point, after_sleep=.65)
                return True
        if (self._label(boxes, "A", (.22, .75, .30, .86))
                and self._label(boxes, "D", (.70, .75, .78, .86))):
            self.click(.963, .225, after_sleep=.55)
            return True
        return False

    def _stage_goal(self, boxes):
        if not self._label(boxes, "阶段目标", (.72, .11, .91, .22), contains=True):
            return False
        frame = self.frame
        timer = self._label(boxes, "还有", (.75, .27, .94, .55), contains=True)
        bottom = timer.center()[1] / self.height - .035 if timer else .29
        area = frame[round(.17 * self.height):round(bottom * self.height),
                     round(.93 * self.width):round(.97 * self.width)]
        hsv = cv2.cvtColor(area, cv2.COLOR_BGR2HSV)
        badge = ((hsv[:, :, 0] < 23) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 145)
        badge &= hsv[:, :, 2] > 155
        count, _, stats, centers = cv2.connectedComponentsWithStats(badge.astype(np.uint8))
        for index in range(1, count):
            if stats[index, cv2.CC_STAT_AREA] > self.width * self.height * .00004:
                x, y = centers[index]
                self.click(int(x + .927 * self.width), int(y + .195 * self.height), after_sleep=.65)
                return True
        return False

    def _fatigue(self, boxes):
        for box in boxes:
            x, y = box.center()
            if .57 < x / self.width < .77 and y / self.height < .11:
                if match := re.fullmatch(r"(\d{1,3})\s*[%％]", box.name):
                    return int(match[1])
        return None

    def _stat(self, boxes, name):
        label = self._label(boxes, name, (.035, .63, .1, .95), contains=True)
        if label:
            return next((int(b.name) for b in boxes if .12 < b.x / self.width < .18
                         and abs(b.center()[1] - label.center()[1]) < .02 * self.height
                         and b.name.isdecimal()), None)
        return None

    def _course_order(self, boxes):
        knowledge = self._stat(boxes, "知识")
        art = self._stat(boxes, "艺术")
        physique = self._stat(boxes, "体魄")
        if knowledge is None or knowledge < 65:
            return ("理科教室", "文科教室", "操场", "家庭餐厅")
        if art is not None and art < 70:
            return ("文科教室", "操场", "理科教室", "家庭餐厅")
        if physique is not None and physique < 35:
            return ("操场", "理科教室", "文科教室", "家庭餐厅")
        if knowledge < 850:
            return ("理科教室", "家庭餐厅", "文科教室", "操场")
        return ("家庭餐厅", "理科教室", "操场", "文科教室")

    def _visit_location(self, boxes):
        if (self._label(boxes, "居家休息", (.7, .4, .99, .98), contains=True)
                or self._label(boxes, "日程安排", (.7, .87, .87, .98), contains=True)
                or self._label(boxes, "阶段目标", (.72, .11, .91, .22), contains=True)):
            return False
        room = next((name for name in COURSES
                     if self._label(boxes, name, (.02, .14, .23, .23))), None)
        slot_tag = self._label(boxes, "占用「", (.72, .2, .99, .85), contains=True)
        if not room and not slot_tag and not self._label(boxes, "赠送礼物", (.19, .3, .4, .46), contains=True):
            return False
        if room:
            self._current_room = room
        if self._label(boxes, "值过高", (.4, .7, .65, .85), contains=True):
            if room:
                self._too_tired_rooms.add(room)
            self.click(.954, .068, after_sleep=.65)
            return True
        if room == "学院商店" and self._need_shop_buy and self._shop_buys < 3:
            if shop := self._label(boxes, "学院商店", (.70, .35, .95, .46)):
                self.click(shop, after_sleep=.75)
                return True
        if lottery := self._label(boxes, "特别刮奖", (.7, .44, .98, .65), contains=True):
            if self._finished_lottery:
                self.click(.954, .068, after_sleep=.7)
            else:
                self.click(lottery, after_sleep=.85)
            return True
        for level, text in enumerate(("初遇", "相知", "熟识", "挚友")):
            if room and self._label(boxes, text, (.7, .125, .93, .205), contains=True):
                self._friend_levels[room] = level
                break
        commission = self._label(boxes, "特别委托", (.19, .23, .96, .8))
        if commission and (self._active_date, room) in self._skipped_commissions:
            commission = None
        invite = self._label(boxes, "邀约出行", (.2, .3, .52, .66), contains=True)
        if action := commission or invite:
            self.click(action, after_sleep=.65)
            return True
        fatigue = self._fatigue(boxes)
        if fatigue is None or fatigue < 88:
            for text in COURSES.get(room, ()):
                if action := self._label(boxes, text, (.67, .22, .95, .87), contains=True):
                    self.click(action, after_sleep=.65)
                    return True
            if slot_tag:
                x, y = slot_tag.center()
                self.click(int(x - .08 * self.width), int(y + .04 * self.height), after_sleep=.65)
                return True
        if room and fatigue is not None and fatigue >= 88:
            self._too_tired_rooms.add(room)
        self.click(.954, .068, after_sleep=.65)
        return True

    def _schedule_save(self, boxes):
        if self._label(boxes, "疲劳度预览", (.53, .035, .64, .112), contains=True):
            return (self._label(boxes, "执行日程", (.78, .85, .99, .98))
                    or self._label(boxes, "保存日程", (.78, .85, .99, .98)))
        return None

    def _schedule_stat(self, boxes, x):
        for box in boxes:
            cx, cy = box.center()
            if abs(cx / self.width - x) < .017 and .88 < cy / self.height < .94:
                value = box.name.replace(",", "")
                if value.isdecimal():
                    return int(value)
        return 0

    def _schedule_money(self, boxes):
        for box in boxes:
            cx, cy = box.center()
            if .8 < cx / self.width < .86 and .035 < cy / self.height < .11:
                value = box.name.replace(",", "")
                if value.isdecimal():
                    return int(value)
        return None

    def _schedule_activity(self, tab, activities):
        self.click(tab, .15, after_sleep=.45)
        cards = self._read()
        if self._tutorial(cards):
            self.click(tab, .15, after_sleep=.45)
            cards = self._read()
        for activity in activities:
            if card := self._label(cards, activity, (.66, .2, .83, .74), contains=True):
                _, y = card.center()
                self.click(round(.896 * self.width), y, after_sleep=.55)
                return True
        return False

    def _commission_tabs(self, date):
        if date in self._schedule_tabs:
            return self._schedule_tabs[date]
        self.click(.654, .15, after_sleep=.45)
        boxes = self._read()
        if self._tutorial(boxes):
            boxes = self._read()
        tab = self.frame[round(.135 * self.height):round(.177 * self.height),
                         round(.64 * self.width):round(.67 * self.width)]
        hsv = cv2.cvtColor(tab, cv2.COLOR_BGR2HSV)
        gold = (hsv[:, :, 0] >= 13) & (hsv[:, :, 0] <= 33) & (hsv[:, :, 1] > 140)
        has_commissions = np.mean(gold) > .10 or bool(self._label(
            boxes, "待执行次数", (.42, .36, .61, .52), contains=True))
        self._schedule_tabs[date] = has_commissions
        if has_commissions:
            self._schedule_commission(boxes)
        return has_commissions

    def _schedule_commission(self, boxes):
        if not self._label(boxes, "周一", (.045, .035, .24, .09), contains=True):
            return
        cards = [b for b in boxes if .68 < b.x / self.width < .85 and .21 < b.y / self.height < .7
                 and len(re.findall(r"[\u4e00-\u9fff]", b.name)) >= 4]
        daytime = (.11, .24, .25, .7)
        if any(self._label(boxes, card.name, daytime) for card in cards):
            return
        for card in cards:
            _, y = card.center()
            self.click(round(.895 * self.width), y, name=card.name, after_sleep=.65)
            updated = self._read()
            if any(self._label(updated, choice.name, daytime) for choice in cards):
                return

    def _schedule_step(self, boxes, save, date):
        slots = [b for b in boxes if .11 < b.x / self.width < .37
                 and .235 < b.center()[1] / self.height < .7 and "暂无安排" in b.name]
        if not slots:
            self.click(save, after_sleep=.8)
            return

        offset = .059 if self._commission_tabs(date) else 0
        fatigue = self._fatigue(boxes)
        if (len(slots) == 5 and self._label(boxes, "04/01", (.045, .03, .22, .095), contains=True)
                and self._schedule_activity(.654, ("文科课程",))):
            return
        self.click(slots[0], after_sleep=.18)
        if fatigue is None:
            fatigue = self._fatigue(self._read())
        if fatigue is None:
            raise RuntimeError("无法读取日程中的疲劳度预览。")
        if fatigue >= 70:
            if self._schedule_activity(.773 + offset, ("居家休息",)):
                return

        knowledge = self._schedule_stat(boxes, .215)
        thinking = self._schedule_stat(boxes, .284)
        art = self._schedule_stat(boxes, .356)
        physique = self._schedule_stat(boxes, .426)
        money = self._schedule_money(boxes)
        science = COURSES["理科教室"]
        work = COURSES["家庭餐厅"]
        study_plan = (.23, .235, .37, .7)
        needs_badges = (knowledge >= 65 and money is not None and money < 20000
                        and not any(self._label(boxes, job, study_plan, contains=True) for job in work))
        if (needs_badges or (knowledge >= 850 and thinking >= 600)) and self._schedule_activity(
                .713 + offset, work):
            return
        if knowledge < 65:
            activities = science
        elif physique < 35:
            activities = COURSES["操场"] + science
        elif art < 70:
            activities = COURSES["文科教室"] + science
        else:
            activities = science
        if self._schedule_activity(.654 + offset, activities):
            return
        raise RuntimeError("找不到可加入日程的课程。")

    def _play_step(self, boxes, date):
        if self._tutorial(boxes):
            return True
        if self._label(boxes, "本次共获取", (.5, .2, .95, .98), contains=True):
            self.click(.954, .068, after_sleep=.7)
            return True
        if self._label(boxes, "故事结局", (.14, .05, .86, .65), contains=True):
            for label in ("返回标题", "返回首页", "返回主界面"):
                if button := self._label(boxes, label, (.25, .7, .99, .98), contains=True):
                    self._story_ending = True
                    self.click(button, after_sleep=1)
                    return True
        if next_month := self._label(boxes, "进入下个月", (.75, .85, .96, .95)):
            self.click(next_month, after_sleep=.8)
            return True
        if offer := self._commission_offer(boxes):
            key = (date or self._active_date, self._current_room)
            if self._commission_unmet(boxes):
                self._skipped_commissions.add(key)
                self.click(.954, .068, after_sleep=.65)
            else:
                self.click(offer, after_sleep=.75)
                if self._commission_offer(self._read()):
                    self._skipped_commissions.add(key)
                    self.click(.954, .068, after_sleep=.65)
            return True
        if option := self._attribute_check(boxes):
            self.click(option, after_sleep=.75)
            return True
        if result := self._attribute_result(boxes):
            self.click(result, after_sleep=.65)
            return True
        if self._lottery_screen(boxes):
            self._play_lottery()
            return True
        if self._shop_screen(boxes):
            self._buy_in_shop(boxes)
            return True
        if save := self._schedule_save(boxes):
            self._schedule_step(boxes, save, date)
            return True
        if self._settings(boxes):
            self._collect_rewards(boxes, self._settings)
            for _ in range(3):
                self.click(.954, .067, after_sleep=.8)
                if self.wait_until(lambda: not self._settings(self._read()), time_out=2):
                    return True
            raise RuntimeError("无法关闭学院手册。")
        if self._label(boxes, "角色档案", (0, 0, .2, .12), contains=True):
            self.click(.954, .067, after_sleep=.65)
            return True
        if self._label(boxes, "档案管理", (0, 0, .2, .12), contains=True):
            self.click(.954, .068, after_sleep=.65)
            return True
        if any(self._label(boxes, title, (0, 0, .2, .13)) for title in REWARD_PAGES):
            self.click(.954, .067, after_sleep=.7)
            return True
        if self._label(boxes, "历程已结束", (0, .45, 1, .85), contains=True):
            self.click(.954, .068, after_sleep=.65)
            return True
        if self._forum(boxes):
            self.click(.81, .876, after_sleep=.3)
            self.click(.857, .095, after_sleep=.55)
            return True
        if self._label(boxes, "课题清单", (0, 0, .2, .12), contains=True):
            claim = self._label(boxes, "领取", (.8, .16, .95, .94), contains=True)
            if claim:
                self.click(claim, after_sleep=.65)
            else:
                self.click(.954, .068, after_sleep=.65)
            return True
        if self._label(boxes, "倍速播放", (.86, .89, .99, .99), contains=True):
            self.send_key("ctrl", down_time=1.4, after_sleep=.25)
            return True
        if focus := self._study_focus(boxes):
            self.click(focus, after_sleep=.65)
            return True
        if option := self._full_choice(boxes):
            self.click(option, after_sleep=.65)
            return True
        if option := self._paper_choice(boxes):
            self.click(option, after_sleep=.65)
            return True
        if execute := self._label(boxes, "确认执行", (.35, .55, .74, .96)):
            self.click(execute, after_sleep=.65)
            return True
        if confirm := self._confirm_event(boxes):
            self.click(confirm, after_sleep=.6)
            return True
        confirm = self._label(boxes, "确定", (.32, .69, .72, .96))
        confirm = confirm or self._label(boxes, "确认", (.43, .77, .57, .92))
        if confirm:
            self.click(confirm, after_sleep=.55)
            return True
        if self._dialogue(boxes):
            return True
        if self._envelope(boxes):
            self.click(.5, .58, after_sleep=.8)
            return True
        if self._label(boxes, "新增物品", (.06, .2, .33, .4), contains=True):
            self.send_key("space", after_sleep=.55)
            return True
        if self._label(boxes, "日常补给") and self._label(boxes, "珍藏道具"):
            self.click(.954, .067, after_sleep=.55)
            return True
        if not date:
            return False
        weekend = any(self._label(boxes, day, (.035, .085, .11, .14)) for day in ("周六", "周日"))
        schedule = self._label(boxes, "日程安排", (.7, .87, .87, .98), contains=True)
        on_map = bool(self._label(boxes, "个人背包", (.48, .02, .66, .13), contains=True))
        outing_btn = next((b for b in boxes if .83 <= b.center()[0] / self.width <= .99
                           and .88 <= b.center()[1] / self.height <= .98
                           and re.search(r"[\u4e00-\u9fff]", b.name)
                           and "回家" not in b.name), None)
        event = (any(self._label(boxes, label, (.83, .88, .99, .98), contains=True) for label in OUTINGS)
                 or (not on_map and bool(self._label(boxes, "就是今天啦", (.72, .25, .96, .45), contains=True)))
                 or (not on_map and bool(schedule) and bool(outing_btn) and "外出" not in outing_btn.name))
        outing = event or bool(self._label(boxes, "外出", (.83, .88, .99, .98), contains=True))
        home = self._label(boxes, "回家", (.82, .88, .99, .98), contains=True)
        if schedule or outing or home:
            checkpoint = (date[0], (date[1] - 1) // 7) if date >= (3, 25) else None
            if checkpoint and checkpoint not in self._reward_checkpoints:
                self._reward_checkpoints.add(checkpoint)
                self.click(.954, .067, after_sleep=.65)
                return True
        if schedule and not (event or weekend or self._label(boxes, "本日暂无法进行", contains=True)):
            self.click(.793, .855, after_sleep=.65)
            return True
        if not on_map and self._stage_goal(boxes):
            return True
        if self._visit_location(boxes):
            return True
        if (not weekend or self._too_tired_rooms) and (rest := self._label(boxes, "居家休息", (.7, .4, .99, .98), contains=True)):
            if (self._fatigue(boxes) or 0) >= 75:
                self.click(rest, after_sleep=.65)
                return True
        if outing:
            self.click(.908, .919, after_sleep=.75)
            return True
        if self._label(boxes, "个人背包", (.48, .02, .66, .13), contains=True):
            if home and not weekend and (self._fatigue(boxes) or 0) >= 85:
                self.click(.918, .868, after_sleep=.65)
                return True
            marker, directions = self._map_marker(boxes)
            if marker:
                self._enter_location(marker)
                return True
            if directions:
                for key in directions:
                    self.send_key(key, down_time=.55, after_sleep=.17)
                return True
            if not home:
                for label in OUTINGS:
                    for box in boxes:
                        bx, by = box.center()
                        rx, ry = bx / self.width, by / self.height
                        if not (.06 <= rx <= .93 and .18 <= ry <= .92):
                            continue
                        if (rx > .71 and ry < .36) or (rx < .26 and ry < .24):
                            continue
                        if any(word in box.name for word in ("阶段目标", "距离", "还有")):
                            continue
                        if label in re.sub(r"\s+", "", box.name):
                            self._enter_location(box)
                            return True
            order = self._course_order(boxes)
            if weekend:
                order = sorted(COURSES, key=lambda name: self._friend_levels.get(name, 0))
            if self._need_shop_buy and self._shop_buys < 3:
                order = ("学院商店", *(name for name in order if name != "学院商店"))
            for name in order:
                if name in self._too_tired_rooms:
                    continue
                if location := self._label(boxes, name, (.06, .2, .93, .97)):
                    self._enter_location(location)
                    return True
            if home:
                self.click(.918, .868, after_sleep=.65)
                return True
        return False

    def run(self):
        self.reset_to_start()
        if not self.verify_start_state():
            raise RuntimeError("请先打开「第二索拉：未名之梦」活动首页或当前旅程。")

        last_date = None
        completed_journeys = 0
        recent = deque(maxlen=40)
        entered = False
        idle_since = monotonic()
        try:
            for _ in range(10000):
                boxes = self._read()
                date = self._date(boxes)
                if date and date != last_date:
                    last_date = date
                    self._active_date = date
                    self._starting_semester = False
                    self._finished_lottery = False
                    self._lottery_index = 0
                    self._too_tired_rooms.clear()
                    self.log_info(f"学期进度 {date[0]:02}/{date[1]:02}")
                if self._lobby(boxes):
                    boxes = self._collect_rewards(boxes, self._lobby)
                    if self._all_rewards_earned():
                        return dict(self._claim_log)
                    resume = self._label(boxes, "继续旅程", (.65, .6, 1, .95), contains=True)
                    if not resume:
                        candidates = self.ocr(.64, .59, .97, .96, match="继续旅程")
                        resume = candidates[0] if candidates else None
                    if entered:
                        finished = self._story_ending or (not resume and last_date and last_date >= (12, 1))
                        if not finished or completed_journeys >= 2:
                            raise RuntimeError(f"旅程已返回活动首页，奖励进度 {self._claim_log}")
                        completed_journeys += 1
                        self._story_ending = False
                        self._friend_levels.clear()
                        self._reward_checkpoints.clear()
                        self._schedule_tabs.clear()
                        self._finished_lottery = False
                        self._skipped_commissions.clear()
                        self._too_tired_rooms.clear()
                        self._current_room = None
                        recent.clear()
                        resume = None
                    start = resume or self._lobby(boxes)
                    self._starting_semester = not resume
                    self.click(start, after_sleep=2)
                    entered = True
                    idle_since = monotonic()
                    continue
                entered = entered or date is not None
                signature = tuple(re.sub(r"\s+", "", b.name) for b in boxes
                                  if re.search(r"[\u4e00-\u9fff]|\d/\d", b.name))
                transition = not date and (len(signature) < 3 or self._letter(boxes))
                if "长按加速" in signature:
                    stuck = len(recent) >= 15 and all(s == signature for s in list(recent)[-15:])
                else:
                    limit = 35 if self._lottery_screen(boxes) else 7
                    stuck = bool(signature) and recent.count(signature) >= limit
                if stuck:
                    raise RuntimeError(f"活动界面重复出现：{'，'.join(signature[:12])}")
                if self._play_step(boxes, date):
                    if self._all_rewards_earned():
                        return dict(self._claim_log)
                    recent.append(signature)
                    idle_since = monotonic()
                elif monotonic() - idle_since > (125 if transition else 25):
                    raise RuntimeError(f"无法识别下一步：{'，'.join(signature[:16])}")
                else:
                    self.sleep(.35)
            raise RuntimeError("超过学期操作次数上限。")
        except RuntimeError:
            self.screenshot("galgame_stopped")
            raise
