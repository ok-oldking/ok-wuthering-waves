import time

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger
from src.char.CharFactory import char_names
from src.scene.WWScene import WWScene
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException, LowHpException

logger = Logger.get_logger(__name__)


class AutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.name = "Auto Combat"
        self.description = "Enable auto combat in Abyss, Game World etc"
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False
        self.default_config.update({
            'Auto Target': True,
            'Use Liberation': True,
            'Check Levitator': True,
            'Low HP Healer Switch': False,
            'Low HP Threshold': 0.4,
        })
        self.config_description = {
            'Auto Target': 'Turn off to enable auto combat only when manually target enemy using middle click',
            'Use Liberation': 'Do not use Liberation in Open World to Save Time',
            'Check Levitator': 'Toggle the levitator and verify if the character is floating',
            'Low HP Healer Switch': 'Interrupt current action and switch to healer when front character HP is low',
            'Low HP Threshold': 'HP ratio (0-1) to trigger the switch',
        }
        self.op_index = 0
        self.char_features_warmed_up = False

    def warm_up_char_features(self):
        if self.char_features_warmed_up:
            return
        try:
            for char_name in char_names:
                self.get_feature_by_name(char_name)
        except Exception as e:
            logger.warning(f'warm_up_char_features failed: {e}')
            return
        self.char_features_warmed_up = True
        logger.info(f'warm_up_char_features loaded {len(char_names)} character templates')

    def run(self):
        self.warm_up_char_features()
        ret = False
        if not self.scene.in_team(self.in_team_and_world):
            return ret
        self.use_liberation = self.config.get('Use Liberation')
        if not self.use_liberation and not self.in_world():  # 仅大世界生效
            self.use_liberation = True
        self._hp_threshold = self.config.get('Low HP Threshold', 0.4)
        self._hp_check_enabled = self.config.get('Low HP Healer Switch', False)
        self._last_low_hp_trigger = 0  # 重置冷却，避免上次战斗的冷却带到本次
        combat_start = time.time()
        while True:
            try:
                # in_combat 内部 (如重锁目标) 和 perform 都可能触发低血量检测
                if not self.in_combat():
                    break
                ret = True
                self.get_current_char().perform()
            except LowHpException as e:
                logger.info(f'low HP interrupt: {e}, switching to healer')
                if not self.switch_to_healer():
                    # 切换失败 → 短冷却防死循环；成功则不设冷却 (on-healer 检查已处理)
                    self._last_low_hp_trigger = time.time()
                    if not any(c and c.is_potential_healer for c in self.chars):
                        # 队伍无治疗位, 关闭检测避免反复打断
                        logger.info('no healer in team, disabling low HP switch')
                        self._hp_check_enabled = False
                continue
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {int(time.time() - combat_start)} {e}')
                break
        self._hp_check_enabled = False  # 先关闭，防止 combat_end 内部 next_frame 触发 LowHpException
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


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=AutoCombatTask, debug=True)
