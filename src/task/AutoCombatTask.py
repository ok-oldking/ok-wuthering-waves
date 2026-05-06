import time

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger
from src.char.CustomRotation import CustomRotation, CustomRotationConfigError
from src.scene.WWScene import WWScene
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

logger = Logger.get_logger(__name__)

CUSTOM_ROTATION_ENABLED = '自定义技能轴'
CUSTOM_ROTATION_SCRIPT = '自定义技能轴脚本'
CUSTOM_ROTATION_EXAMPLE = """# 自定义队伍技能轴，每行一个动作，默认示例全部注释，不会执行
# switch:1 / 切人:1        切到1号位，switch不带数字则使用原来的自动切人
# tap:3@0.15 / 普攻:3@0.15 普攻点击3次，每次间隔0.15秒
# attack:0.5@0.1 / 连续普攻:0.5@0.1  连续普攻0.5秒，每次间隔0.1秒
# resonance / 共鸣技能     共鸣技能
# liberation / 大招        共鸣解放
# echo / 声骸              声骸技能
# heavy:0.6 / 重击:0.6     重击0.6秒
# dodge:0.1 / 闪避:0.1     闪避后等待0.1秒
# jump:0.1 / 跳跃:0.1      跳跃后等待0.1秒
# sleep:1.2 / 等待:1.2     等待1.2秒
"""


class AutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.name = "Auto Combat"
        self.description = "自动战斗；展开本卡片可配置自定义队伍技能轴"
        self.instructions = """自定义技能轴位置：
在 Auto Combat 卡片中展开配置，打开“自定义技能轴”，然后在“自定义技能轴脚本”里填写队伍轴。

常用写法：
切人:1
普攻:3@0.15
共鸣技能
等待:0.3
闪避:0.1
切人:2
大招
声骸

说明：
每行一个动作，# 开头是注释。
普攻:3@0.15 表示普攻点 3 次，每次间隔 0.15 秒。
连续普攻:0.5@0.1 表示连续普攻 0.5 秒，每次间隔 0.1 秒。
切人:1/2/3 表示指定切到对应队伍位置。
"""
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False
        self.default_config.update({
            'Auto Target': True,
            'Use Liberation': True,
            'Check Levitator': True,
            CUSTOM_ROTATION_ENABLED: False,
            CUSTOM_ROTATION_SCRIPT: CUSTOM_ROTATION_EXAMPLE,
        })
        self.config_description = {
            'Auto Target': 'Turn off to enable auto combat only when manually target enemy using middle click',
            'Use Liberation': 'Do not use Liberation in Open World to Save Time',
            'Check Levitator': 'Toggle the levitator and verify if the character is floating',
            CUSTOM_ROTATION_ENABLED: '开启后按下方队伍技能轴逐行执行，关闭时使用角色内置自动战斗逻辑',
            CUSTOM_ROTATION_SCRIPT: '每行一个动作；支持 switch/tap/attack/resonance/liberation/echo/heavy/dodge/jump/sleep，也支持中文别名，# 开头为注释',
        }
        self.config_type[CUSTOM_ROTATION_SCRIPT] = {'type': 'text_edit'}
        self.custom_rotation = CustomRotation(self)
        self.op_index = 0

    def run(self):
        ret = False
        if not self.scene.in_team(self.in_team_and_world):
            return ret
        self.use_liberation = self.config.get('Use Liberation')
        if not self.use_liberation and not self.in_world():  # 仅大世界生效
            self.use_liberation = True
        use_custom_rotation = self.config.get(CUSTOM_ROTATION_ENABLED)
        if use_custom_rotation:
            try:
                self.custom_rotation.load(self.config.get(CUSTOM_ROTATION_SCRIPT, ''), reset=True)
            except CustomRotationConfigError as e:
                self.log_error(f'自定义技能轴配置错误，已回退到内置自动战斗: {e}')
                use_custom_rotation = False
        combat_start = time.time()
        while self.in_combat():
            ret = True
            try:
                if use_custom_rotation:
                    self.custom_rotation.perform_next()
                else:
                    self.get_current_char().perform()
            except CustomRotationConfigError as e:
                self.log_error(f'自定义技能轴执行错误，已回退到内置自动战斗: {e}')
                use_custom_rotation = False
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {int(time.time() - combat_start)} {e}')
                break
        if ret:
            self.combat_end()
        return ret

    def realm_perform(self):
        if not self.last_is_click:
            if self.op_index % 10 == 0:
                self.send_key_and_wait_animation('4', self.in_illusive_realm, enter_animation_wait=0.2)
            else:
                self.click()
        else:
            if self.available('liberation'):
                self.send_key_and_wait_animation(self.get_liberation_key(), self.in_illusive_realm)
            elif self.available('echo'):
                self.send_key(self.get_echo_key())
            elif self.available('resonance'):
                self.send_key(self.get_resonance_key())
            elif self.is_con_full() and self.in_team()[0]:
                self.send_key_and_wait_animation('2', self.in_illusive_realm)
        self.last_is_click = not self.last_is_click
        self.op_index += 1
        self.sleep(0.02)
