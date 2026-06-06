import time

from src.char.BaseChar import SwitchPriority
from src.task.AutoCombatTask import AutoCombatTask, CUSTOM_AXIS_ROLE_FLOW_ACTION_NAMES, logger
from src.task.BaseCombatTask import NotInCombatException, CharDeadException

LIBERATION_ACTION_NAMES = {
    'r', 'lib', 'liberation', 'ult', '大招', '解放', '共鸣解放',
} | CUSTOM_AXIS_ROLE_FLOW_ACTION_NAMES
LIBERATION_STATE_NAMES = {'lib', 'liberation', 'r', '大招', '解放'}


class TeamAxisAutoCombatTask(AutoCombatTask):
    """AutoCombatTask with optional team-axis and per-slot liberation controls.

    When "Auto Detect Team Axis" is enabled, the task detects the current
    3-character team once at combat start and uses the matching custom axis
    profile for that combat. While axis mode is enabled, normal auto-combat is
    not allowed to cast Liberation automatically; only explicit R/Liberation
    steps in the axis can release Liberation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visible = True
        self.name = "自动战斗"
        self.description = "实时触发自动战斗；配置了队伍轴时会自动匹配并执行启动轴/循环轴"
        self.default_config.update({
            'Auto Detect Team Axis': True,
            'Reset Axis Loop On Combat Start': True,
            'Use Liberation Slot 1': True,
            'Use Liberation Slot 2': True,
            'Use Liberation Slot 3': True,
            'Release Liberation Slot 1': True,
            'Release Liberation Slot 2': True,
            'Release Liberation Slot 3': True,
        })
        self.config_description.update({
            'Auto Detect Team Axis': 'Turn on to detect the current 3-character team at combat start and use the matching custom axis. When on, normal auto-combat will not cast Liberation automatically; only explicit R/Liberation steps in the axis can release it. Turn off to use the original auto-combat behavior.',
            'Reset Axis Loop On Combat Start': 'When enabled, every new combat starts the custom axis from the first matching step, and combat end clears the current loop state.',
            'Use Liberation Slot 1': 'Original auto-combat mode only: allow Liberation for the character in team slot 1. Ignored while Auto Detect Team Axis is on.',
            'Use Liberation Slot 2': 'Original auto-combat mode only: allow Liberation for the character in team slot 2. Ignored while Auto Detect Team Axis is on.',
            'Use Liberation Slot 3': 'Original auto-combat mode only: allow Liberation for the character in team slot 3. Ignored while Auto Detect Team Axis is on.',
            'Release Liberation Slot 1': 'Axis mode only: allow custom-axis R/Liberation actions for the character in team slot 1.',
            'Release Liberation Slot 2': 'Axis mode only: allow custom-axis R/Liberation actions for the character in team slot 2.',
            'Release Liberation Slot 3': 'Axis mode only: allow custom-axis R/Liberation actions for the character in team slot 3.',
        })

    def run(self):
        self.warm_up_char_features()
        ret = False
        if not self.scene.in_team(self.in_team_and_world):
            return ret
        if not self.in_combat():
            return ret
        if self._reset_axis_loop_on_combat_start():
            self._reset_axis_loop('combat_start')
        while self.in_combat():
            ret = True
            try:
                current_char = self.get_current_char()
                if self._team_axis_enabled() and self._get_aemeath_denia_chisa_axis_team():
                    self.info_set('Team Axis', 'Aemeath-Denia-Chisa')
                if self._custom_axis_enabled() and self.run_custom_axis_once():
                    continue
                self._set_auto_liberation_for_char(current_char)
                current_char.perform()
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {int(time.time() - self.combat_start)} {e}')
                break
        if ret:
            if self._reset_axis_loop_on_combat_start():
                self._reset_axis_loop('combat_end')
            self.combat_end()
        return ret

    def _reset_axis_loop_on_combat_start(self):
        return bool(self.config.get('Reset Axis Loop On Combat Start', True))

    def _reset_axis_loop(self, reason):
        self.custom_axis_cursor = 0
        self.custom_axis_startup_cursor = 0
        self.custom_axis_loop_cursor = 0
        self.custom_axis_startup_done = False
        self.info_set('Custom Axis Loop', f'Reset: {reason}')
        self.log_debug(f'custom axis loop reset: {reason}')

    def _global_liberation_allowed(self):
        enabled = bool(self.config.get('Use Liberation', True))
        if not enabled and not self.in_world():  # keep the original rule: only open world can disable global Liberation
            enabled = True
        return enabled

    def _slot_liberation_config(self, char, prefix):
        if char is None:
            return False
        slot = int(getattr(char, 'index', 0)) + 1
        if slot < 1 or slot > 3:
            return False
        return bool(self.config.get(f'{prefix} Slot {slot}', True))

    def _axis_mode_active(self):
        return self._auto_detect_team_axis_enabled()

    def _auto_liberation_enabled_for_char(self, char):
        if self._axis_mode_active():
            # Axis mode must be deterministic: no automatic Liberation outside
            # of explicit R/Liberation steps arranged in the axis profile/script.
            return False
        return self._global_liberation_allowed() and self._slot_liberation_config(char, 'Use Liberation')

    def _axis_liberation_enabled_for_char(self, char):
        return self._global_liberation_allowed() and self._slot_liberation_config(char, 'Release Liberation')

    def _set_auto_liberation_for_char(self, char):
        self.use_liberation = self._auto_liberation_enabled_for_char(char)
        if char is not None:
            self.info_set(f'Slot {char.index + 1} Auto Liberation', self.use_liberation)
        if self._axis_mode_active():
            self.info_set('Axis Blocks Auto Liberation', True)
        return self.use_liberation

    def _set_axis_liberation_for_char(self, char):
        self.use_liberation = self._axis_liberation_enabled_for_char(char)
        if char is not None:
            self.info_set(f'Slot {char.index + 1} Axis Liberation', self.use_liberation)
        return self.use_liberation

    def _execute_custom_axis_action(self, char, action):
        name, _ = self._parse_custom_axis_action(action)
        if name in LIBERATION_ACTION_NAMES:
            if not self._set_axis_liberation_for_char(char):
                self.log_info(f'custom axis skip liberation by slot config: slot {char.index + 1} {char}.{action}')
                return True
        return super()._execute_custom_axis_action(char, action)

    def _axis_state_value(self, char_name, state_name):
        state = state_name.lower()
        if state in LIBERATION_STATE_NAMES:
            char = self._find_axis_char(char_name)
            if char is not None and not self._axis_liberation_enabled_for_char(char):
                return 0
        return super()._axis_state_value(char_name, state_name)

    def _auto_detect_team_axis_enabled(self):
        return bool(self.config.get('Auto Detect Team Axis', True))

    def _team_axis_enabled(self):
        return self._auto_detect_team_axis_enabled() and super()._team_axis_enabled()

    def _custom_axis_enabled(self):
        return self._auto_detect_team_axis_enabled() and super()._custom_axis_enabled()

    def get_team_axis_switch_priority(self, candidate, current_char=None, has_intro=False, target_low_con=False):
        if not self._auto_detect_team_axis_enabled():
            return None
        return super().get_team_axis_switch_priority(
            candidate,
            current_char=current_char,
            has_intro=has_intro,
            target_low_con=target_low_con,
        )

    def _axis_or_char_switch_priority(self, char, current_char, has_intro=False, target_low_con=False):
        axis_priority = self.get_team_axis_switch_priority(
            char,
            current_char=current_char,
            has_intro=has_intro,
            target_low_con=target_low_con,
        )
        if axis_priority is not None:
            return axis_priority
        return char.get_switch_priority(
            current_char=current_char,
            has_intro=has_intro,
            target_low_con=target_low_con,
        )

    def _choose_intro_switch_target(self, must_targets, normal_targets):
        if must_targets:
            return self._oldest_switch_target(must_targets)
        for char_type in ('is_main_dps', 'is_sub_dps', 'is_healer'):
            target = self._oldest_switch_target([char for char in normal_targets if getattr(char, char_type)])
            if target:
                return target
        return None

    def _choose_switch_target(self, current_char, has_intro, target_low_con=False):
        if not self._auto_detect_team_axis_enabled():
            return super()._choose_switch_target(
                current_char,
                has_intro,
                target_low_con=target_low_con,
            )

        candidates = [
            char for char in self.chars
            if char is not None and char != current_char
        ]
        if not candidates:
            return current_char

        must_targets = []
        normal_targets = []
        no_targets = []
        for char in candidates:
            switch_priority = self._axis_or_char_switch_priority(
                char,
                current_char=current_char,
                has_intro=has_intro,
                target_low_con=target_low_con,
            )
            self.log_debug(f'team_axis switch_next_char hook: {char} priority {switch_priority}')
            if switch_priority == SwitchPriority.MUST:
                must_targets.append(char)
            elif switch_priority == SwitchPriority.NO:
                no_targets.append(char)
            else:
                normal_targets.append(char)

        if has_intro:
            return self._choose_intro_switch_target(must_targets, normal_targets) or current_char

        if must_targets:
            candidates = must_targets
        else:
            candidates = normal_targets
            if not candidates:
                return current_char

        candidates_without_switch_cd = [char for char in candidates if not self._target_has_switch_cd(char)]
        if candidates_without_switch_cd:
            candidates = candidates_without_switch_cd

        return self._choose_switch_target_by_buff_time(current_char, candidates)
