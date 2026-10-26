import time

from ok import TriggerTask, Logger, TaskDisabledException
from src.char.CharFactory import char_names
from src.combat.FKeyWatcher import FKeyWatcher
from src.scene.WWScene import WWScene
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

logger = Logger.get_logger(__name__)

F_KEY_EXPIRE = 10


class AutoCombatTask(BaseCombatTask, TriggerTask):
    owns_switch_healer_config = True
    _reset_combat_on_run = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.name = "⚔️ Auto Combat"
        self.description = "Enable auto combat in Abyss, Game World etc"
        self.last_is_click = False
        self.default_config.update({
            'Auto Target': True,
            'Use Liberation': True,
            'Check Levitator': True,
            'Switch to Healer before and after Combat': True,
            'Start Combat with F Key': False,
            'F Key Start Delay': 0.0,
        })
        self.config_description = {
            'Auto Target': 'Turn off to enable auto combat only when manually target enemy using middle click',
            'Use Liberation': 'Do not use Liberation in Open World to Save Time',
            'Check Levitator': 'Toggle the levitator and verify if the character is floating',
            'Switch to Healer before and after Combat': 'Better Chance to Keep Character Alive',
            'Start Combat with F Key': 'After pressing F in a challenge or domain, start combat without waiting for a target or health bar. Only recommended for hard combat content such as Matrix, Tower of Adversity and Whimpering Wastes. F is ignored in the open world, but turning this off there is still recommended',
            'F Key Start Delay': 'Seconds to wait after pressing F before starting combat',
        }
        self.op_index = 0
        self.char_features_warmed_up = False
        self.f_key_watcher = FKeyWatcher(self.is_game_foreground)
        self.f_key_handled = 0.0

    def is_game_foreground(self):
        return self.hwnd is not None and self.hwnd.is_foreground()

    def should_start_combat_by_key(self):
        if not self.config.get('Start Combat with F Key'):
            return False
        pressed = self.f_key_watcher.last_press
        if pressed <= self.f_key_handled:
            return False
        waited = time.time() - pressed
        try:
            delay = max(0.0, float(self.config.get('F Key Start Delay') or 0))
        except (TypeError, ValueError):
            delay = 0.0
        if waited < delay:
            return False
        self.f_key_handled = pressed
        if waited >= delay + F_KEY_EXPIRE:
            return False
        if self.is_open_world_auto_combat():
            # F also picks up items and talks to NPCs in the open world
            self.log_info('F key ignored in open world')
            return False
        return True

    def disable(self):
        # The UI thread only invalidates state; the executor performs the reset.
        self._reset_combat_on_run = True
        super().disable()

    def reset_auto_combat(self, reason):
        self._reset_combat_on_run = False
        self.reset_to_false(reason)
        self.chars = [None, None, None]
        self.freeze_durations = []

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
        if self._reset_combat_on_run:
            self.reset_auto_combat('auto combat restarted')
            self.f_key_handled = time.time()
        if self.config.get('Start Combat with F Key'):
            self.f_key_watcher.start()
        else:
            # presses made while the option is off must not count once it is turned on
            self.f_key_handled = time.time()
        try:
            return self.run_auto_combat()
        except TaskDisabledException:
            self.reset_auto_combat('auto combat disabled')
            raise

    def run_auto_combat(self):
        self.warm_up_char_features()
        ret = False
        if not self.scene.in_team(self.in_team_and_world):
            self.reset_auto_combat('not in team and world')
            return ret
        self.use_liberation = self.config.get('Use Liberation')
        if not self.use_liberation and not self.in_world():  # 仅大世界生效
            self.use_liberation = True
        combat_start = time.time()
        switched_to_healer = False
        while self.in_combat():
            ret = True
            try:
                if not switched_to_healer:
                    self.switch_healer()
                    switched_to_healer = True
                self.get_current_char().perform()
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {int(time.time() - combat_start)} {e}')
                break
        if ret:
            # F presses made before or during this combat must not start another one
            self.f_key_handled = time.time()
            self.combat_end()
            self.switch_healer()
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
