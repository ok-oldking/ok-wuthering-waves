# ChangeEchoTask.py
import re
import time
import os

from qfluentwidgets import FluentIcon

from ok import FindFeature, Logger
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)

number_pattern = re.compile(r"^[\d.%]+$")
property_pattern = re.compile(r"^\D*$")


class ChangeEchoTask(BaseWWTask, FindFeature):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "批量修改声骸主属性(仅支持简中游戏语言)"
        self.description = "点击B进入背包, 在过滤器中选择需要修改主属性的声骸, 并按照等级从0排序后开始."
        self.icon = FluentIcon.CUT
        self.group_name = "强化声骸"
        self.group_icon = FluentIcon.ADD
        self.scene: WWScene | None = None
        self.fail_reason = ""
        self.add_text_fix(
            {'凝夜自霜': '凝夜白霜', '主属性灭伤害加成': '主属性湮灭伤害加成', "灭伤害加成": "主属性湮灭伤害加成",
             '主属性行射伤害加成': '主属性衍射伤害加成'})
        self.default_config.update({
            '目标属性': '攻击',
        })
        self.config_type["目标属性"] = {'type': "drop_down",
                                        'options': ['攻击', '暴击伤害', '暴击', '生命', '防御',
                                                    '共鸣效率', "冷凝伤害加成",
                                                    "热熔伤害加成",
                                                    "导电伤害加成",
                                                    "气动伤害加成", "衍射伤害加成", "湮灭伤害加成", ]}

    def find_echo_enhance(self):
        return self.ocr(0.82, 0.86, 0.97, 0.96, match='培养')

    def is_0_level(self):
        return self.ocr(0.66, 0.48, 0.77, 0.56, match=re.compile('声骸技能'))

    def run(self):
        self.info_set('成功声骸数量', 0)
        while True:
            enhance = self.find_echo_enhance()
            if not enhance:
                raise Exception('必须在背包声骸界面过滤后开始!')
            current_level = self.is_0_level()
            if not current_level:
                total = self.info_get('成功声骸数量') + self.info_get('失败声骸数量')
                if self.debug:
                    self.screenshot('无可强化声骸')
                self.log_info(f'无可修改声骸, 任务结束! 强化{total}个, 符合条件{self.info_get("成功声骸数量")}个',
                              notify=True)
                if self.info_get('成功声骸数量') >= 1:
                    try:
                        os.startfile(os.path.abspath("screenshots"))
                    except Exception as e:
                        self.log_error(f"无法打开截图文件夹: {e}")
                return
            start = time.time()
            while time.time() - start < 5:
                if enhance:
                    self.click(enhance, after_sleep=0.5)
                enhance = self.find_echo_enhance()
                if not enhance:
                    break
            target_main = self.config.get('目标属性')

            self.wait_ocr(match='声骸强化', raise_if_not_found=True)
            self.sleep(0.5)
            current_main = self.wait_ocr(0.09, 0.20, 0.15, 0.26)
            if not current_main:
                raise Exception('找不到当前主属性!')
            if target_main in current_main[0].name:
                raise Exception('目标属性和当前属性相同, 请修改声骸过滤条件!')
            self.click(0.04, 0.41)
            self.wait_ocr(match='主音属性', raise_if_not_found=True)
            self.sleep(0.8)
            self.click(0.5, 0.76)
            target = self.wait_ocr(match=re.compile(target_main), raise_if_not_found=True)
            self.sleep(0.1)
            self.click(target, after_sleep=0.5)
            self.wait_click_ocr(match='确认', after_sleep=2)
            self.wait_click_ocr(0.37, 0.82, 0.64, 0.99, match='数据重构', after_sleep=0.5, raise_if_not_found=True)
            self.wait_ocr(match='获得声骸', raise_if_not_found=True)
            self.esc()
            self.info_incr('成功声骸数量')

    def esc(self):
        start = time.time()
        while not self.find_echo_enhance() and time.time() - start < 5:
            self.send_key('esc', after_sleep=1)
        self.sleep(0.1)
