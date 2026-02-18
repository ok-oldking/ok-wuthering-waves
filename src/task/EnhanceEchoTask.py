# EnhanceEchoTask.py
import re
import time
import os

from qfluentwidgets import FluentIcon

from ok import FindFeature, Logger
from ok.util.file import clear_folder
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)

number_pattern = re.compile(r"^[\d.%]+$")
property_pattern = re.compile(r"^\D*$")


class EnhanceEchoTask(BaseWWTask, FindFeature):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "批量强化声骸(仅支持简中游戏语言)"
        self.description = "点击B进入背包, 在过滤器中选择需要强化的声骸, 并按照等级从0排序后开始."
        self.icon = FluentIcon.ADD
        self.group_name = "强化声骸"
        self.group_icon = FluentIcon.ADD
        self.scene: WWScene | None = None
        self.fail_reason = ""
        self.default_config.update({
            '必须有双爆': True,
            '双爆出现之前必须全有效词条': True,
            '双爆总计>=': 13.8,
            '首条暴击>=': 6.9,
            '首条暴击伤害>=': 13.8,
            '无效词条>=则终止': 3,
            '第一条必须为有效词条': True,
            '有效词条': ['暴击', '暴击伤害', '攻击百分比']
        })
        self.config_type["有效词条"] = {'type': "multi_selection",
                                        'options': ['暴击伤害', '暴击', '攻击百分比', '生命百分比', '防御百分比',
                                                    '共鸣效率', '普攻伤害加成',
                                                    '重击伤害加成', '共鸣解放伤害加成',
                                                    '共鸣技能伤害加成']}
        self.config_description = {
            '必须有双爆': '如果开启，声骸最终必须同时拥有暴击和暴击伤害。如果剩余孔位不足以凑齐双爆，则丢弃',
            '双爆出现之前必须全有效词条': '开启后，在暴击或暴击伤害词条出现之前，前面的所有词条必须都在有效词条列表中',
            '双爆总计>=': '当声骸同时存在暴击和爆伤时，需要满足 暴击 + (爆伤/2) >= 此数值',
            '首条暴击>=': '仅检查第一条出现的暴击是否满足条件',
            '首条暴击伤害>=': '仅检查第一条出现的暴击伤害是否满足条件',
            '无效词条>=则终止': '当检测到的无效词条数量达到此数值时，停止强化并丢弃',
            '第一条必须为有效词条': '如果开启，第一个副词条必须在有效词条列表中且符合数值要求，否则直接丢弃',
            '有效词条': '定义哪些属性被视为有效',
        }

    def find_echo_enhance(self):
        return self.ocr(0.82, 0.86, 0.97, 0.96, match='培养')

    def is_0_level(self):
        return self.ocr(0.66, 0.48, 0.77, 0.56, match=re.compile('声骸技能'))

    def run(self):
        self.info_set('成功声骸数量', 0)
        self.info_set('失败声骸数量', 0)
        clear_folder('screenshots')
        while True:
            enhance = self.find_echo_enhance()
            if not enhance:
                raise Exception('必须在背包声骸界面过滤后开始!')
            current_level = self.is_0_level()
            if not current_level:
                total = self.info_get('成功声骸数量') + self.info_get('失败声骸数量')
                if self.debug:
                    self.screenshot('无可强化声骸')
                self.log_info(f'无可强化声骸, 任务结束! 强化{total}个, 符合条件{self.info_get("成功声骸数量")}个',
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

            while True:
                start_wait = time.time()
                add_mat = None
                have_add_mat = False
                while time.time() - start_wait < 5:
                    add_mat = self.find_add_mat()
                    if add_mat:
                        have_add_mat = True
                        self.click(add_mat, after_sleep=0.3)
                    else:
                        break
                if not have_add_mat:
                    raise Exception('强化方式需要改为阶段放入!')

                self.wait_click_ocr(0.17, 0.88, 0.29, 0.96, match=['强化并调谐'], raise_if_not_found=True,
                                    settle_time=0.1,
                                    after_sleep=1.5)
                while handle := self.wait_ocr(0.24, 0.18, 0.75, 0.93,
                                              match=['本次登录不再提示', '调谐成功', '点击任意位置返回'],
                                              time_out=1):
                    if handle[0].name == '本次登录不再提示':
                        click = handle[0]
                        click.width = 1
                        click.x -= click.height * 1.1
                        self.click(click, after_sleep=0.5)
                        self.wait_click_ocr(0.24, 0.18, 0.75, 0.93, match='确认', after_sleep=0.5)
                    elif handle[0].name in ['点击任意位置返回', '调谐成功']:
                        self.click(handle, after_sleep=0.5)

                texts = self.ocr(0.11, 0.29, 0.36, 0.51)
                properties = self.find_boxes(texts, match=property_pattern)
                values = self.find_boxes(texts, match=number_pattern)
                self.info_set('属性', properties)
                self.info_set('值', values)

                if not self.check_echo_stats(properties, values):
                    self.trash_and_esc()
                    break

                if len(values) == 5:
                    self.lock_and_esc()
                    break

    def check_echo_stats(self, properties, values):
        self.fail_reason = ""
        invalid_count = 0
        total_count = len(values)

        crit_rate_val = 0
        crit_dmg_val = 0
        has_crit_rate = False
        has_crit_dmg = False

        checked_first_crit_rate = False
        checked_first_crit_dmg = False
        has_encountered_crit = False

        valid_stats = self.config.get('有效词条') or []

        for i in range(total_count):
            p = properties[i].name
            v = parse_number(values[i].name)

            is_valid_prop = True

            if p in ['攻击', '生命', '防御']:
                if '%' not in values[i].name:
                    is_valid_prop = False
                    self.log_debug(f'非百分比属性, {p} 不符合条件')
                else:
                    p += '百分比'

            is_crit_stat = p in ['暴击', '暴击伤害']

            if self.config.get(
                    '双爆出现之前必须全有效词条') and '暴击' in valid_stats and '暴击伤害' in valid_stats and not has_encountered_crit:
                if not is_crit_stat:
                    if p not in valid_stats:
                        self.fail_reason = f'双爆前含无效_{p}'
                        self.log_info(f'双爆出现前存在无效词条 {p}, 丢弃')
                        return False
                else:
                    has_encountered_crit = True

            if is_valid_prop and p not in valid_stats:
                is_valid_prop = False
                self.log_debug(f'非有效词条, {p} 不符合条件')

            if p == '暴击':
                has_crit_rate = True
                crit_rate_val += v
                if '暴击' in valid_stats and not checked_first_crit_rate:
                    checked_first_crit_rate = True
                    if v < self.config.get('首条暴击>='):
                        is_valid_prop = False
                        self.log_info(f'首条暴击 {v} < {self.config.get("首条暴击>=")}')

            elif p == '暴击伤害':
                has_crit_dmg = True
                crit_dmg_val += v
                if '暴击伤害' in valid_stats and not checked_first_crit_dmg:
                    checked_first_crit_dmg = True
                    if v < self.config.get('首条暴击伤害>='):
                        is_valid_prop = False
                        self.log_info(f'首条暴击伤害 {v} < {self.config.get("首条暴击伤害>=")}')

            if not is_valid_prop:
                invalid_count += 1

        self.info_set('不符合条件属性', invalid_count)

        if self.config.get('必须有双爆'):
            missing_crit = (0 if has_crit_rate else 1) + (0 if has_crit_dmg else 1)
            remaining_slots = 5 - total_count
            if remaining_slots < missing_crit:
                self.fail_reason = f'无法凑齐双爆_缺{missing_crit}'
                self.log_info(f'无法凑齐双爆 (缺{missing_crit}种, 剩{remaining_slots}孔), 丢弃')
                return False

        if has_crit_rate and has_crit_dmg:
            total_score = crit_rate_val + (crit_dmg_val / 2)
            if total_score < self.config.get('双爆总计>='):
                self.fail_reason = f'双爆总计不足_{total_score:.1f}'
                self.log_info(f'双爆总计 {total_score:.1f} < {self.config.get("双爆总计>=")}，丢弃')
                return False

        if total_count == 1 and self.config.get('第一条必须为有效词条') and invalid_count == 1:
            self.fail_reason = '首条无效'
            self.log_info('第一条必须为有效词条, 丢弃')
            return False

        if invalid_count >= self.config.get('无效词条>=则终止'):
            self.fail_reason = f'{invalid_count}无效词条终止'
            self.log_info(f'{invalid_count}无效词条>=则终止, 丢弃')
            return False

        return True

    def find_add_mat(self):
        return self.wait_ocr(0.22, 0.67, 0.31, 0.72, match=['阶段放入'], time_out=1)

    def esc(self):
        start = time.time()
        while not self.find_echo_enhance() and time.time() - start < 5:
            self.send_key('esc', after_sleep=1)
        self.sleep(0.1)

    def trash_and_esc(self):
        self.info_incr('失败声骸数量')
        start = time.time()
        success = False
        while time.time() - start < 5:
            drop_status = self.find_best_match_in_box(self.get_box_by_name('echo_dropped').scale(1.05),
                                                      ['echo_dropped', 'echo_not_dropped'], threshold=0.7)
            if not drop_status:
                raise Exception('无法找到声骸弃置状态!')
            if drop_status.name == 'echo_not_dropped':
                self.send_key('z', after_sleep=1)
            else:
                self.log_info('成功弃置!')
                success = True
                break
        if not success:
            raise Exception('弃置失败!')
        safe_reason = re.sub(r'[<>:"/\\|?*]', '', self.fail_reason)
        self.screenshot_echo(f'failed/{self.info_get("失败声骸数量")}_{safe_reason}')
        self.esc()
        self.log_info('不符合条件 丢弃')
        self.wait_ocr(0.82, 0.86, 0.97, 0.96, match='培养', settle_time=0.1)

    def screenshot_echo(self, name):
        echo = self.box_of_screen(0.09, 0.09, 0.37, 0.55).crop_frame(self.frame)
        self.screenshot(name=name, frame=echo)

    def lock_and_esc(self):
        self.info_incr('成功声骸数量')
        start = time.time()
        success = False
        while time.time() - start < 5:
            drop_status = self.find_best_match_in_box(self.get_box_by_name('echo_locked').scale(1.05),
                                                      ['echo_locked', 'echo_not_locked'], threshold=0.7)
            if not drop_status:
                raise Exception('无法找到声骸上锁状态!')
            if drop_status.name == 'echo_not_locked':
                self.send_key('c', after_sleep=1)
            else:
                self.log_info('成功弃置!')
                success = True
                break
        if not success:
            raise Exception('上锁失败!')
        self.screenshot_echo(f'success/{self.info_get("成功声骸数量")}')
        self.log_info('成功并上锁')
        self.esc()
        self.wait_ocr(0.82, 0.86, 0.97, 0.96, match='培养', settle_time=0.1)


def parse_number(text):
    try:
        return float(text.split('%')[0])
    except (ValueError, IndexError):
        return 0.0
