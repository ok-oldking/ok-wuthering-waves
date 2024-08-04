import re

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

        self.config_type = {}
        for key in self.default_config.keys():
            self.config_type[key] = {'type': "multi_selection", 'options': self.sets}
        self.first_echo_x = 326 / 3840
        self.first_echo_y = 178 / 2160
        self.echo_x_distance = (2215 - 343) / 7 / 3840
        self.echo_y_distance = (1678 - 421) / 4 / 2160
        self.echo_per_row = 8
        self.confirmed = False

    def run(self):
        while self.loop_merge():
            pass

    def loop_merge(self):
        add = self.wait_feature('data_merge_hcenter_vcenter')
        if not add:
            raise Exception('请在5合1界面开始,并保持声骸未添加状态')
        self.click(add)
        self.wait_feature('data_merge_selection', raise_if_not_found=True, threshold=0.8)
        self.sleep(0.5)
        row = 0
        col = 0
        add_count = 0

        while add_count < 5:
            if col >= 8:
                row += 1
                col = 0
                self.log_info(f'next row {row, col}')
            x, y = self.get_pos(row, col)
            col += 1
            # self.click_relative(x - 0.01, y - 0.01)
            # self.sleep(0.1)
            # self.sleep(0.5)
            lock = self.wait_until(self.find_lock, pre_action=lambda: self.click_relative(x - 0.01, y + 0.01),
                                   wait_until_before_delay=0.8, raise_if_not_found=True)
            if lock.name == 'echo_locked':
                self.log_info(f'五合一完成,合成{self.info.get("合成数量", 0)},加锁{self.info.get("加锁数量", 0)}',
                              notify=True)
                return False

            texts = self.ocr(0.60, 0.40, 0.83, 0.76, name='echo_stats', target_height=720, log=True)
            sets = find_boxes_by_name(texts, self.sets)
            if not sets:
                self.log_error(f'无法识别声骸套装', notify=True)
                return False
            set_name = sets[0].name

            cost = self.find_cost(texts)
            if not cost:
                self.log_error(f'无法识别声骸COST', notify=True)
                return False

            main_stat_boundary = self.box_of_screen(0.66, 0.40, 0.77, 0.47)
            main_stat_box = find_boxes_within_boundary(texts, main_stat_boundary)
            if not main_stat_box or len(main_stat_box) > 1 or main_stat_box[0].name not in self.main_stats:
                self.log_error(f'无法识别声骸主属性{main_stat_box}', notify=True)
                return False
            main_stat = main_stat_box[0].name

            config_name = f'锁定_{cost}C_{main_stat}'

            sets_to_lock = self.config.get(config_name, [])
            if set_name in sets_to_lock:
                self.log_info(f'需要加锁 {config_name} {set_name}')
                self.click_relative(x, y)
                self.sleep(1)
                self.click(lock)
                locked = self.wait_feature('echo_locked', threshold=0.9)
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
