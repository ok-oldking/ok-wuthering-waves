# EnhanceEchoTask.py
import re
import time
import os

from qfluentwidgets import FluentIcon

from ok import FindFeature, Logger
from ok.feature.Box import get_bounding_box
from ok.util.file import clear_folder
from src.scene.WWScene import WWScene
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)

number_pattern = re.compile(r"^[\d.%％ ]+$")
property_pattern = re.compile(r"[\u4e00-\u9fff]{2,}")


class EnhanceEchoTask(BaseWWTask, FindFeature):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "批量强化声骸(游戏与okww语言必须为简体/繁体中文)"
        self.description = "点击B进入背包, 在过滤器中选择需要强化的声骸, 并按照等级从0排序后开始."
        self.icon = FluentIcon.ADD
        self.group_name = "强化声骸"
        self.group_icon = FluentIcon.ADD
        self.fail_reason = ""
        self.supported_languages = ["zh_CN", "zh_TW"]

        self.all_props = [
            '暴击伤害', '暴击', '共鸣效率', '攻击百分比', '生命百分比', '防御百分比',
            '普攻伤害加成', '重击伤害加成',
            '共鸣解放伤害加成', '共鸣技能伤害加成',
            '攻击', '生命', '防御'
        ]

        self.default_config.update({
            '方案选择': '经典双爆方案',
            '必须词条': ['暴击', '暴击伤害'],
            '可选词条': ['攻击百分比'],
            '可选词条数量 >=': 3,
            '前置检查': '在双爆出现前',
            '暴击数值 >=': '6.3%',
            '爆伤数值 >=': '12.6%',
            '双爆总计 >=': 13.8,
            'Pause after Success': True,
        })

        self.config_type["方案选择"] = {
            'type': 'preset_manager',
            'linked_keys': [
                '必须词条', '可选词条', '可选词条数量 >=', '前置检查',
                '暴击数值 >=', '爆伤数值 >=', '双爆总计 >=', 'Pause after Success'
            ]
        }
        self.config_type["必须词条"] = {
            'type': 'multi_selection',
            'options': self.all_props
        }
        self.config_type["可选词条"] = {
            'type': 'multi_selection',
            'options': self.all_props
        }
        self.config_type["前置检查"] = {
            'type': 'radio_group',
            'options': ['不限制', '在双爆出现前', '在必须词条出现前']
        }
        self.config_type["暴击数值 >="] = {
            'type': 'drop_down',
            'options': ['6.3%', '6.9%', '7.5%', '8.1%', '8.7%', '9.3%', '9.9%', '10.5%']
        }
        self.config_type["爆伤数值 >="] = {
            'type': 'drop_down',
            'options': ['12.6%', '13.8%', '15%', '16.2%', '17.4%', '18.6%', '19.8%', '21%']
        }

        self.config_description = {
            '方案选择': '保存或切换用户自定义的整套强化要求过滤方案。',
            '必须词条': '剩余孔位无法凑齐已选项，或满级时未凑齐，均丢弃。',
            '可选词条': '声骸满级时，需凑齐符合数量的任意词条，否则丢弃。',
            '可选词条数量 >=': '若剩余孔位无法凑齐该数量，则提前丢弃。',
            '前置检查': '是否需要在暴击或爆伤或必须词条项出现前，前面的所有词条都必须在已选词条里，否则丢弃。',
            '暴击数值 >=': '若暴击在必须词条中，则检查暴击数值是否满足，否则丢弃。',
            '爆伤数值 >=': '若爆伤在必须词条中，则检查爆伤数值是否满足，否则丢弃。',
            '双爆总计 >=': '若双爆均在必须词条中，检查 暴击数值 + (爆伤数值/2) 的总和是否 >= 此数值，否则丢弃。',
            'Pause after Success': 'When a success occurs, send notification and pause task',
        }

    def find_echo_enhance(self):
        return self.ocr(0.82, 0.86, 0.97, 0.96, match='培养')

    def is_0_level(self):
        return self.ocr(0.65, 0.35, 1, 0.57, match=re.compile('声骸技能'))

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
                have_add_mat = False
                while time.time() - start_wait < 5:
                    add_mat = self.find_add_mat()
                    if add_mat:
                        have_add_mat = True
                        self.click(add_mat, after_sleep=0.3)
                    else:
                        self.next_frame()
                        if have_add_mat:
                            break
                if not have_add_mat:
                    raise Exception('强化设置需要开启阶段放入!')

                if not self.wait_click_ocr(0.17, 0.88, 0.29, 0.96, match=['强化并调谐'],
                                           settle_time=0.1,
                                           after_sleep=1.5):
                    if self.ocr(0.17, 0.88, 0.29, 0.96, match=['强化']):
                        raise Exception('强化设置需要开启同步调谐!')
                    else:
                        raise Exception('找不到 强化并调谐!')
                while handle := self.wait_ocr(0.24, 0.18, 0.75, 0.98,
                                              match=[re.compile('不再提示'), '调谐成功', re.compile('点击任')],
                                              time_out=2):
                    if handle[0].name in ['本次登录不再提示', '本次登入不再提示']:
                        click = handle[0]
                        click.width = 1
                        click.x -= click.height * 1.1
                        self.click(click, after_sleep=0.5)
                        self.click(self.find_confirm(), after_sleep=0.5)
                    elif handle[0].name in ['点击任意位置返回', '调谐成功']:
                        self.click(handle, after_sleep=1)
                    else:
                        self.sleep(0.5)
                self.sleep(0.1)
                texts = self.ocr(0.09, 0.3, 0.40, 0.53)
                self.log_info(f'ocr values: {texts}')
                properties = [p for p in self.find_boxes(texts, match=property_pattern) if '辅音' not in p.name]
                for p in properties:
                    match = property_pattern.search(p.name)
                    if match:
                        p.name = match.group()
                values = self.find_boxes(texts, match=number_pattern)
                self.info_set('属性', properties)
                self.info_set('值', values)

                if not self.check_echo_stats(properties, values):
                    self.trash_and_esc()
                    break

                if len(properties) >= 5:
                    self.lock_and_esc()
                    break

    def find_confirm(self):
        button_box = self.box_of_screen(0.60, 0.65, 0.82, 0.82)
        if confirm := self.find_one('echo_enhance_confirm', box=button_box, threshold=0.7):
            return [confirm]
        return self.ocr(box=button_box, match='确认')

    # ---------- 核心判断逻辑 ----------
    def check_echo_stats(self, properties, values):
        self.fail_reason = ""
        paired_stats = self._pair_stats(properties, values)
        total_count = len(paired_stats)
        remaining_slots = 5 - total_count

        required_set = set(self.config.get('必须词条') or [])
        optional_set = set(self.config.get('可选词条') or [])
        all_selected = required_set | optional_set

        parsed = []
        for raw_name, val_str in paired_stats:
            normalized, is_crit_rate, is_crit_dmg = self._normalize_prop(raw_name, val_str)
            value = parse_number(val_str)
            parsed.append({
                'raw': raw_name,
                'name': normalized,
                'value': value,
                'is_crit_rate': is_crit_rate,
                'is_crit_dmg': is_crit_dmg,
                'in_required': normalized in required_set,
                'in_optional': normalized in optional_set,
                'in_selected': normalized in all_selected,
            })

        # ---- 前置检查 ----
        mode = self.config.get('前置检查')
        if mode != '不限制':
            trigger_props = None
            if mode == '在双爆出现前':
                trigger_props = {'暴击', '暴击伤害'}
            elif mode == '在必须词条出现前':
                trigger_props = required_set

            if trigger_props:
                for s in parsed:
                    if s['name'] in trigger_props:
                        break
                    if not s['in_selected']:
                        self.fail_reason = f'前置检查失败：{s["name"]}不在已选词条中'
                        self.log_info(f'前置检查失败：{s["name"]}不在已选词条中')
                        return False

        # ---- 暴击数值 >= ----
        if '暴击' in required_set:
            threshold = parse_number(self.config.get('暴击数值 >='))
            found = next((s for s in parsed if s['is_crit_rate']), None)
            if found and found['value'] < threshold:
                self.fail_reason = f'暴击{found["value"]}% < {threshold}%'
                self.log_info(f'暴击不达标: {found["value"]}%')
                return False

        # ---- 爆伤数值 >= ----
        if '暴击伤害' in required_set:
            threshold = parse_number(self.config.get('爆伤数值 >='))
            found = next((s for s in parsed if s['is_crit_dmg']), None)
            if found and found['value'] < threshold:
                self.fail_reason = f'爆伤{found["value"]}% < {threshold}%'
                self.log_info(f'爆伤不达标: {found["value"]}%')
                return False

        # ---- 双爆合计 >= ----
        if '暴击' in required_set and '暴击伤害' in required_set:
            total_threshold = self.config.get('双爆总计 >=')
            cr = next((s['value'] for s in parsed if s['is_crit_rate']), None)
            cd = next((s['value'] for s in parsed if s['is_crit_dmg']), None)
            if cr is not None and cd is not None:
                total = cr + cd / 2
                if total < total_threshold:
                    self.fail_reason = f'双爆合计{total:.1f} < {total_threshold}'
                    self.log_info('双爆合计不达标')
                    return False

        # ---- 必须词条剩余孔位预测 ----
        required_total = len(required_set)
        if required_total > 0:
            appeared = sum(1 for s in parsed if s['in_required'])
            if remaining_slots < required_total - appeared:
                self.fail_reason = '剩余孔位不足凑齐必须词条'
                self.log_info('必须词条无法凑齐')
                return False

        # ---- 可选词条数量预测 ----
        opt_target = self.config.get('可选词条数量 >=')
        current_opt = sum(1 for s in parsed if s['in_optional'])
        if current_opt + remaining_slots < opt_target:
            self.fail_reason = '可选词条数量不足'
            self.log_info('可选词条预测不达标')
            return False

        return True

    def _pair_stats(self, properties, values):
        unmatched = values.copy()
        result = []
        for prop in properties:
            if unmatched:
                closest = min(unmatched, key=lambda v, p=prop: abs(p.y - v.y))
                result.append((prop.name, closest.name))
                unmatched.remove(closest)
            else:
                result.append((prop.name, "0"))
        return result

    # ---------- 属性标准化（查表法，低复杂度版） ----------
    PROP_MAP = [
        ('暴击伤害', '暴击伤害', False, True),
        ('暴击', '暴击', True, False),
        ('攻击', None, False, False),
        ('生命', None, False, False),
        ('防御', None, False, False),
        ('效率', '共鸣效率', False, False),
        ('普攻', '普攻伤害加成', False, False),
        ('重击', '重击伤害加成', False, False),
        ('解放', '共鸣解放伤害加成', False, False),
        ('技能', '共鸣技能伤害加成', False, False),
    ]

    def _normalize_prop(self, raw_name, val_str):
        for keyword, standard, is_crit_rate, is_crit_dmg in self.PROP_MAP:
            if keyword not in raw_name:
                continue
            if standard is not None:
                return standard, is_crit_rate, is_crit_dmg
            suffix = '百分比' if ('%' in val_str or '％' in val_str) else ''
            return f'{keyword}{suffix}', is_crit_rate, is_crit_dmg
        return raw_name, False, False

    def find_add_mat(self):
        return self.wait_ocr(0.09, 0.6, 0.38, 0.86, match=['阶段放入'], time_out=1)

    def esc(self):
        start = time.time()
        while not self.find_echo_enhance() and time.time() - start < 10:
            self.send_key('esc', interval=4, after_sleep=0.2)
        self.sleep(0.1)

    def trash_and_esc(self):
        self.info_incr('失败声骸数量')
        start = time.time()
        success = False
        drop_status_box = get_bounding_box([
            self.get_box_by_name('echo_dropped'),
            self.get_box_by_name('echo_not_dropped'),
        ]).scale(1.05)
        while time.time() - start < 5:
            drop_status = self.find_best_match_in_box(drop_status_box,
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
        lock_status_box = get_bounding_box([
            self.get_box_by_name('echo_locked'),
            self.get_box_by_name('echo_not_locked'),
        ]).scale(1.05)
        while time.time() - start < 5:
            drop_status = self.find_best_match_in_box(lock_status_box,
                                                      ['echo_locked', 'echo_not_locked'], threshold=0.7)
            if not drop_status:
                raise Exception('无法找到声骸上锁状态!')
            if drop_status.name == 'echo_not_locked':
                self.send_key('c', after_sleep=1)
            else:
                self.log_info('成功上锁!')
                success = True
                break
        if not success:
            raise Exception('上锁失败!')
        self.screenshot_echo(f'success/{self.info_get("成功声骸数量")}')
        self.log_info('成功并上锁')
        if self.config.get('Pause after Success'):
            self.log_info('符合条件的声骸，已暂停任务', notify=True)
            self.pause()
        self.esc()
        self.wait_ocr(0.82, 0.86, 0.97, 0.96, match='培养', settle_time=0.1)


def parse_number(text):
    try:
        return float(text.replace('％', '%').split('%')[0])
    except (ValueError, IndexError):
        return 0.0
