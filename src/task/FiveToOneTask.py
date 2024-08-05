import re

import cv2
import numpy as np

from ok.feature.Box import Box, find_boxes_by_name, find_boxes_within_boundary
from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask

logger = get_logger(__name__)


class FiveToOneTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "数据坞五合一 + 自动上锁, 游戏语言必须为简体中文,必须16:9分辨率"
        self.name = "在数据坞五合一界面启动"
        self.default_config = {
            '锁定_1C_生命': [],
            '锁定_1C_防御': [],
            '锁定_1C_攻击': [
                '凝夜白霜', '熔山裂谷', '彻空冥雷', '啸谷长风', '浮星祛暗', '沉日劫明', '隐世回光', '轻云出月',
                '不绝余音'],
            '锁定_3C_生命': [],
            '锁定_3C_防御': [],
            '锁定_3C_攻击': [],
            '锁定_3C_气动伤害加成': ['啸谷长风', '轻云出月'],
            '锁定_3C_热熔伤害加成': ['熔山裂谷', '轻云出月'],
            '锁定_3C_导电伤害加成': ['彻空冥雷', '轻云出月'],
            '锁定_3C_衍射伤害加成': ['浮星祛暗', '轻云出月'],
            '锁定_3C_湮灭伤害加成': ['沉日劫明', '轻云出月'],
            '锁定_3C_冷凝伤害加成': ['凝夜白霜', '轻云出月'],
            '锁定_3C_共鸣效率': [
                '凝夜白霜', '熔山裂谷', '彻空冥雷', '啸谷长风', '浮星祛暗', '沉日劫明', '隐世回光', '轻云出月',
                '不绝余音'],
            '锁定_4C_暴击': ['凝夜白霜', '熔山裂谷', '彻空冥雷', '啸谷长风', '浮星祛暗', '沉日劫明', '隐世回光',
                             '轻云出月',
                             '不绝余音'],
            '锁定_4C_暴击伤害': ['凝夜白霜', '熔山裂谷', '彻空冥雷', '啸谷长风', '浮星祛暗', '沉日劫明', '隐世回光',
                                 '轻云出月',
                                 '不绝余音'],
            '锁定_4C_治疗效果加成': ['隐世回光'],
            '锁定_4C_生命': [],
            '锁定_4C_防御': [],
            '锁定_4C_攻击': [],
        }
        self.sets = [
            '凝夜白霜', '熔山裂谷', '彻空冥雷', '啸谷长风', '浮星祛暗', '沉日劫明', '隐世回光', '轻云出月', '不绝余音']

        self.main_stats = ["攻击", "防御", "生命", "共鸣效率", "冷凝伤害加成", "热熔伤害加成", "导电伤害加成",
                           "气动伤害加成", "衍射伤害加成", "湮灭伤害加成", "治疗效果加成", "暴击", "暴击伤害"]
        self.fix_map = {'凝夜自霜': '凝夜白霜', '灭伤害加成': '湮灭伤害加成', '行射伤害加成': '衍射伤害加成'}

        self.config_type = {}
        for key in self.default_config.keys():
            self.config_type[key] = {'type': "multi_selection", 'options': self.sets}
        self.first_echo_x = 326 / 3840
        self.first_echo_y = 178 / 2160
        self.echo_x_distance = (2215 - 343) / 7 / 3840
        self.echo_y_distance = (1678 - 421) / 4 / 2160
        self.echo_per_row = 8
        self.confirmed = False
        self.current_cost = 0

    def run(self):
        self.current_cost = 0
        while self.loop_merge():
            pass

    def incr_cost_filter(self):
        if self.current_cost == 0:
            self.current_cost = 1
        elif self.current_cost == 1:
            self.current_cost = 3
        elif self.current_cost == 3:
            self.current_cost = 4
        else:
            return False
        self.set_filter(self.current_cost)
        return True

    def set_filter(self, cost):
        self.log_info(f'increase cost filter {cost}')
        self.click_relative(0.04, 0.91)
        self.sleep(1)
        boxes = self.ocr(0.11, 0.31, 0.90, 0.88, target_height=720, log=True)
        self.click(find_boxes_by_name(boxes, names='重置'), after_sleep=1)
        self.click(find_boxes_by_name(boxes, names='五星'), after_sleep=1)
        self.click(find_boxes_by_name(boxes, names=re.compile(f'ost{cost}')), after_sleep=1)
        self.click(find_boxes_by_name(boxes, names='确定'), after_sleep=1)
        self.click_empty_area()

    def click_empty_area(self):
        self.click_relative(0.9, 0.51, after_sleep=1)

    def check_ui(self):
        put = self.ocr(0.46, 0.64, 0.58, 0.69)
        if len(put) == 1:
            if put[0].name == "清除":
                self.click(put, after_sleep=1)
                return True
            elif put[0].name == '自动放入':
                return True

    def fix_ocr_texts(self, texts):
        for text in texts:
            if fix := self.fix_map.get(text.name):
                text.name = fix

    def loop_merge(self):
        if self.current_cost == 0:
            time_out = 0
        else:
            time_out = 10
        add = self.wait_until(self.check_ui, post_action=self.click_empty_area, time_out=time_out)
        if not add:
            raise Exception('请在5合1界面开始,并保持声骸未添加状态')
        self.click_relative(0.53, 0.20)
        self.wait_feature('data_merge_selection', raise_if_not_found=True, threshold=0.75,
                          post_action=self.click_empty_area, time_out=15)
        self.sleep(0.5)

        if self.current_cost == 0:
            self.incr_cost_filter()
        row = 0
        col = 0
        add_count = 0

        while add_count < 5:
            if col >= 8:
                row += 1
                col = 0
                self.log_info(f'next row {row, col}')
                if row == 6:
                    self.log_error(f'无法凑够五个声骸, 请退出重新开始', notify=True)
                    return False
            x, y = self.get_pos(row, col)
            col += 1
            lock = self.wait_until(self.find_lock, pre_action=lambda: self.click_relative(x - 0.01, y + 0.01),
                                   wait_until_before_delay=0.8, raise_if_not_found=True)
            if lock.name == 'echo_locked':
                if self.incr_cost_filter():
                    col = 0
                    row = 0
                    continue
                else:
                    self.log_info(f'五合一完成,合成{self.info.get("合成数量", 0)},加锁{self.info.get("加锁数量", 0)}',
                                  notify=True)
                    return False

            texts = self.ocr_echo_texts()
            sets = find_boxes_by_name(texts, self.sets)
            if not sets:
                set_name = self.find_set_by_template()
                if not set_name:
                    self.log_error(f'无法识别声骸套装, 需要打开角色声骸界面,右上角点击切换一下简述', notify=True)
                    return False
            else:
                set_name = sets[0].name

            cost = self.find_cost(texts)
            if not cost:
                self.log_error(f'无法识别声骸COST', notify=True)
                return False

            main_stat_boundary = self.box_of_screen(0.66, 0.40, 0.77, 0.47)
            main_stat_box = find_boxes_within_boundary(texts, main_stat_boundary)
            main_stat = "None"
            if main_stat_box and len(main_stat_box) == 1:
                main_stat = main_stat_box[0].name
            if main_stat not in self.main_stats:
                self.log_error(f'无法识别声骸主属性{main_stat_box}', notify=True)
                return False

            config_name = f'锁定_{cost}C_{main_stat}'

            sets_to_lock = self.config.get(config_name, [])
            if set_name in sets_to_lock:
                self.log_info(f'需要加锁 {config_name} {set_name}')
                self.click_relative(x, y)
                self.sleep(1)
                locked = self.wait_feature('echo_locked', threshold=0.9, pre_action=lambda: self.click(lock),
                                           wait_until_before_delay=1.5)
                if not locked:
                    self.log_info(f'加锁失败 {config_name} {set_name}', notify=True)
                    return False
                self.info['加锁数量'] = self.info.get('加锁数量', 0) + 1
                continue
            add_count += 1

        self.click_relative(0.79, 0.91)
        self.sleep(0.5)
        self.click_relative(0.79, 0.91)  # merge
        if not self.confirmed:
            confirm = self.wait_feature('data_merge_confirm_hcenter_vcenter', time_out=3, raise_if_not_found=False)
            if confirm:
                self.click_relative(0.44, 0.55)
                self.sleep(0.5)
                self.click_box(confirm, relative_x=-1)
            self.confirmed = True
        self.wait_ocr(0.45, 0.33, 0.55, 0.39, match='获得声骸', raise_if_not_found=True, time_out=15)
        self.sleep(1)
        self.click_relative(0.79, 0.91)
        self.info['合成数量'] = self.info.get('合成数量', 0) + 1
        return True

    def find_set_by_template(self):
        box = self.get_box_by_name('box_set_name')
        max_conf = 0
        max_name = None
        for i in range(len(self.sets)):
            feature = self.find_one(f'set_name_{i}', box=box, threshold=0.65, mask_function=mask_circle)
            if feature and feature.confidence > max_conf:
                max_conf = feature.confidence
                max_name = self.sets[i]
        logger.info(f'find_set_by_template: {max_name} {max_conf}')
        return max_name

    def ocr_echo_texts(self):
        texts = self.ocr(0.60, 0.40, 0.83, 0.76, name='echo_stats', target_height=720, log=True)
        self.fix_ocr_texts(texts)
        return texts

    def find_cost(self, texts):
        cost_boundary = self.box_of_screen(0.80, 0.24, 0.83, 0.29, name='cost_boundary')
        # cost_boxes = find_boxes_within_boundary(texts, cost_boundary)
        cost_boxes = self.ocr(box=cost_boundary, log=True)
        for box in cost_boxes:
            extract = extract_number(box.name)
            if extract is not None:
                return extract

    def find_lock(self) -> Box:
        data_merge_locked = self.find_one('echo_locked', threshold=0.75)
        data_merge_unlocked = self.find_one('echo_unlocked', threshold=0.75)
        self.log_debug(f'find lock {data_merge_locked} {data_merge_unlocked}')
        if data_merge_locked and data_merge_unlocked:
            if data_merge_locked.confidence > data_merge_unlocked.confidence:
                return data_merge_locked
            else:
                return data_merge_unlocked
        else:
            return data_merge_locked or data_merge_unlocked

    def get_pos(self, row, col):
        return self.first_echo_x + col * self.echo_x_distance, self.first_echo_y + row * self.echo_y_distance


def extract_number(text):
    # Use regular expression to find the first occurrence of a number
    match = re.search(r'\d+', text)
    if match:
        return int(match.group())
    return None


def mask_circle(image):
    # Get the dimensions of the image
    height, width = image.shape[:2]

    # Calculate the center and axes of the ellipse
    center = (width // 2, height // 2)
    axes = (width // 2, height // 2)

    # Create a mask with the same dimensions as the image
    mask = np.zeros((height, width), dtype=np.uint8)

    # Draw the ellipse on the mask
    cv2.ellipse(mask, center, axes, 0, 0, 360, (255), thickness=-1)
    return mask
