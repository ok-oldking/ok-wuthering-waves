import cv2
import numpy as np

import re
from ok import find_boxes_by_name, find_boxes_within_boundary, Logger
from src.task.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)
chinese_regex = re.compile(r'[\u4e00-\u9fff]{5,12}')


class FiveToOneTask(BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "游戏语言必须为简体中文,必须16:9分辨率,使用1600x900以上分辨率, 勾选需要的, 没勾的都会自动合成"
        self.name = "数据坞五合一"
        self.default_config = {
        }
        self.sets = [
            '凝夜白霜', '熔山裂谷', '彻空冥雷', '啸谷长风', '浮星祛暗', '沉日劫明', '隐世回光', '轻云出月', '不绝余音',
            '凌冽决断之心',
            '此间永驻之光', '幽夜隐匿之帷', '高天共奏之曲', '无惧浪涛之勇', '流云逝尽之空']
        # , '愿戴荣光之旅',   '奔狼燎原之焰',

        self.main_stats = ["攻击力百分比", "生命值百分比", "防御力百分比", "暴击率", "暴击伤害", "共鸣效率",
                           "冷凝伤害加成",
                           "热熔伤害加成",
                           "导电伤害加成",
                           "气动伤害加成", "衍射伤害加成", "湮灭伤害加成", "治疗效果加成"]
        self.all_stats = []
        self.black_list = ["主属性生命值", "主属性攻击力", "主属性防御力"]
        for main_stat in self.main_stats:
            self.all_stats.append(re.compile("主属性" + main_stat))
        for black in self.black_list:
            self.all_stats.append(re.compile(black))

        self.add_text_fix(
            {'凝夜自霜': '凝夜白霜', '主属性灭伤害加成': '主属性湮灭伤害加成', "灭伤害加成": "主属性湮灭伤害加成",
             '主属性行射伤害加成': '主属性衍射伤害加成'})

        self.config_type = {}
        self.claim_handled = False
        for set_name in self.sets:
            self.default_config[set_name] = []
        for key in self.default_config.keys():
            self.config_type[key] = {'type': "multi_selection", 'options': self.main_stats}

    def run(self):
        self.log_debug(f"all_stats: {self.all_stats}")
        self.log_info("开始任务")
        self.ensure_main()
        self.log_info("在主页")
        self.back()
        self.wait_click_ocr(match="数据坞", box="right", raise_if_not_found=True, settle_time=0.2)
        self.wait_ocr(match="数据坞", box="top_left", raise_if_not_found=True, settle_time=0.2)
        self.click_relative(0.04, 0.56, after_sleep=0.5)
        self.wait_click_ocr(match="批量融合", box="bottom_right", raise_if_not_found=True, settle_time=0.2)
        self.loop_merge()
        self.log_info("五合一完成!")

    def loop_merge(self):
        name_box = self.box_of_screen(0.11, 0.19, 0.87, 0.75)
        for set_name in self.sets:
            self.merge_set(name_box, set_name, 1)
            self.merge_set(name_box, set_name, 2)

    def merge_set(self, name_box, set_name, step):
        keeps = self.config.get(set_name, [])
        if step == 2 and "攻击力百分比" not in keeps:  # 4C攻击力
            self.log_info("没有选择攻击力百分比, 跳过第二步")
            return
        self.click_relative(0.03, 0.91, after_sleep=0.3)
        if step == 1:
            self.click_relative(0.62, 0.82, after_sleep=0.01)  # 重置

        self.click_relative(0.20, 0.71, after_sleep=0.01)  # 1c
        self.click_relative(0.47, 0.71, after_sleep=0.01)  # 3c
        if step == 1:
            self.click_relative(0.71, 0.71, after_sleep=0.01)  # 4c
        if step == 1:
            self.click_relative(0.895, 0.57, after_sleep=0.5)  # 滚动
            self.wait_click_ocr(box=name_box, match=re.compile(set_name), raise_if_not_found=True,
                                after_sleep=0.2)
            self.wait_feature("merge_echo_check", box=name_box, raise_if_not_found=True)
        self.click_relative(0.895, 0.74, after_sleep=0.5)  # 滚动
        choices = self.ocr(box=name_box, match=self.all_stats)
        if step == 1:
            if len(choices) != 16:
                raise Exception(f"属性列表识别失败! {choices}")
            for choice in choices:
                in_keep = False
                in_black_list = False
                for black in self.black_list:
                    if black in choice.name and "百分比" not in choice.name:
                        in_black_list = True
                        break
                if in_black_list:
                    self.log_debug(f'跳过黑名单 {choice.name}')
                    continue
                for keep in keeps:
                    if keep in choice.name:
                        in_keep = True
                        break
                if not in_keep:
                    self.click_box(choice, after_sleep=0.01)
                    self.log_info(f"不在配置 {set_name} {choice.name} 选择合成!")
        else:
            for choice in choices:
                if "攻击力百分比" in choice.name:
                    self.click_box(choice, after_sleep=0.01)
                    break
        self.click_relative(0.81, 0.84, after_sleep=0.5)
        while True:
            self.click_relative(0.26, 0.91, after_sleep=0.5)  # 全选
            self.click_relative(0.78, 0.9, after_sleep=1)
            if not self.claim_handled:
                if confirm := self.ocr(match="确认", box="bottom_right"):
                    self.click_relative(0.49, 0.55, after_sleep=0.1)
                    self.click_box(confirm, after_sleep=0.5)
                    self.claim_handled = True
            if self.ocr(match="批量融合", box="bottom_right"):
                self.click_relative(0.26, 0.91, after_sleep=0.5)
                self.log_info(f"{set_name} 不够5个")
                break  # 没有更多
            self.wait_ocr(match="获得声骸", box="top", raise_if_not_found=True, settle_time=1)
            self.click_relative(0.53, 0.05, after_sleep=0.5)
            self.click_relative(0.68, 0.91, after_sleep=0.5)  # 批量融合
