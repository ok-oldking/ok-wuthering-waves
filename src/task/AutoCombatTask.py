import json
import re
import time
from pathlib import Path

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger
from src.char.BaseChar import SwitchPriority
from src.char.CharFactory import char_names
from src.scene.WWScene import WWScene
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

logger = Logger.get_logger(__name__)

DEFAULT_CUSTOM_AXIS_SCRIPT = """# 自定义队伍轴，每行格式：角色: 动作1, 动作2 | 条件 条件表达式
# 角色支持：1/2/3、爱弥斯/aemeath、达尼亚/denia、千咲/chisa
# 动作支持：e/resonance/共鸣, e_anim, e:秒, r/liberation/解放, q/echo/声骸, attack:秒, attack_until_condition:秒, attack_until_con:秒, heavy:秒, heavy_until_condition:秒, heavy_until_con:秒, role_flow/角色流程, dodge:秒, jump, wait:秒, f, f_until:秒
# 动作:秒 表示动作发出后占用/等待指定秒数；attack:秒 为持续普攻；wait:秒 表示空等；*_until_* 的秒数表示持续/超时
# 条件支持：角色.buff, 角色.lib2, 角色.协奏满, 角色.大招, 角色.技能, 角色.声骸，例如：千咲.buff<=2
千咲: q, r, e | 条件 千咲.buff<=2
达尼亚: e, r, q | 条件 达尼亚.buff<=2 && 千咲.buff>2
爱弥斯: e, r, q, attack:0.8
爱弥斯: r | 条件 爱弥斯.lib2<=1
"""

CUSTOM_AXIS_FAILED_ACTION_STRATEGIES = [
    'Retry Then Continue',
    'Retry Then Skip Step',
    'Retry Then Restart Axis',
    'Retry Then Switch Next Script Role',
    'Retry Then Fallback Normal Combat',
]

CUSTOM_AXIS_ACTION_RETRY_INTERVAL = 0.05
CUSTOM_AXIS_TARGET_ENEMY_INTERVAL = 0.5
CUSTOM_AXIS_RETRY_UNTIL_SUCCESS_CONFIG = 'Custom Axis Retry Until Success'

CUSTOM_AXIS_ROLE_FLOW_ACTION_NAMES = {
    'role_flow', 'char_flow', 'character_flow', 'perform', 'flow',
    '角色流程', '自动流程', '角色自动流程',
}

CUSTOM_AXIS_ANIMATED_RESONANCE_ACTION_NAMES = {
    'e_anim', 'e_animation', 'res_anim', 'resonance_anim', 'skill_anim',
}

CUSTOM_AXIS_ACTION_NAMES = {
    'e', 'e_wait', 'e_anim', 'e_animation', 'res', 'resonance', 'res_anim', 'resonance_anim',
    'skill', 'skill_wait', 'skill_anim', 'r', 'lib', 'liberation', 'ult', 'q', 'echo',
    'attack', 'click', 'a', 'normal', 'attack_until_condition', 'attack_until_con', 'attack_until_con_full',
    'normal_until_con', 'heavy', 'heavy_attack', 'heavy_until_condition',
    'heavy_until_con', 'heavy_until_con_full',
    'dodge', 'dash', 'evade', 'jump', 'space', 'wait', 'sleep',
    'f', 'break', 'f_break', 'f_until', 'f_auto', 'f_loop', '共鸣', '共鸣技能', '技能', '技能等待', '大招', '解放', '共鸣解放',
    '声骸', '普攻', '平a', '普攻到条件满足', '平a到条件满足', '普攻到协奏满', '平a到协奏满', '重击', '重击到条件满足', '重击到协奏满', '闪避', '跳起', '跳跃',
    '等待', '交互', '持续交互', '持续f',
} | CUSTOM_AXIS_ROLE_FLOW_ACTION_NAMES

CUSTOM_AXIS_CHAR_ALIASES = {
    'aemeath': 'aemeath', '爱弥斯': 'aemeath', '愛彌斯': 'aemeath',
    'augusta': 'augusta', '奥古斯塔': 'augusta',
    'baizhi': 'baizhi', '白芷': 'baizhi',
    'brant': 'brant', '布兰特': 'brant',
    'calcharo': 'calcharo', '卡卡罗': 'calcharo',
    'camellya': 'camellya', '椿': 'camellya',
    'cantarella': 'cantarella', '坎特蕾拉': 'cantarella',
    'carlotta': 'carlotta', '珂莱塔': 'carlotta',
    'cartethyia': 'cartethyia', '卡提希娅': 'cartethyia',
    'changli': 'changli', '长离': 'changli',
    'chisa': 'chisa', '千咲': 'chisa',
    'chixia': 'chixia', '炽霞': 'chixia',
    'ciaccona': 'ciaccona', '夏空': 'ciaccona',
    'danjin': 'danjin', '丹瑾': 'danjin',
    'denia': 'denia', '达尼亚': 'denia', '達尼亞': 'denia',
    'douling': 'douling', '卜灵': 'douling', '灯灯': 'douling',
    'encore': 'encore', '安可': 'encore',
    'galbrena': 'galbrena', '嘉贝莉娜': 'galbrena',
    'havocrover': 'havocrover', '暗主': 'havocrover',
    'spectrorover': 'havocrover', '光主': 'havocrover',
    'aerorover': 'havocrover', 'windrover': 'havocrover', '风主': 'havocrover',
    'hiyuki': 'hiyuki', '釉瑚': 'hiyuki',
    'iuno': 'iuno', '尤诺': 'iuno',
    'jianxin': 'jianxin', '鉴心': 'jianxin',
    'jinhsi': 'jinhsi', '今汐': 'jinhsi',
    'jiyan': 'jiyan', '忌炎': 'jiyan',
    'linnai': 'linnai', '琳奈': 'linnai',
    'lupa': 'lupa', '露帕': 'lupa',
    'roccia': 'roccia', '洛可可': 'roccia',
    'sanhua': 'sanhua', '散华': 'sanhua',
    'shorekeeper': 'shorekeeper', '守岸人': 'shorekeeper',
    'taoqi': 'taoqi', '桃祈': 'taoqi',
    'verina': 'verina', '维里奈': 'verina',
    'xiangliyao': 'xiangliyao', '相里要': 'xiangliyao',
    'yinlin': 'yinlin', '吟霖': 'yinlin',
    'yuanwu': 'yuanwu', '渊武': 'yuanwu',
    'zani': 'zani', '赞妮': 'zani',
    'zhezhi': 'zhezhi', '折枝': 'zhezhi',
}


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
            'Team Axis': True,
            'Team Axis Mode': 'Auto',
            'Axis Buff Refresh Seconds': 2.0,
            'Custom Team Axis': False,
            'Custom Axis Auto Enable File': True,
            'Custom Axis Script File': 'configs/custom_axis_script.txt',
            'Custom Axis Profiles File': 'configs/custom_axis_profiles.json',
            'Custom Axis Match Team Order': False,
            'Custom Axis Script': DEFAULT_CUSTOM_AXIS_SCRIPT,
            'Custom Axis Step Timeout': 1.2,
            'Custom Axis Action Retry Count': 1,
            'Custom Axis Failed Action Strategy': 'Retry Then Continue',
        })
        self.config_description = {
            'Auto Target': 'Turn off to enable auto combat only when manually target enemy using middle click',
            'Use Liberation': 'Do not use Liberation in Open World to Save Time',
            'Check Levitator': 'Toggle the levitator and verify if the character is floating',
            'Team Axis': 'Enable team-wide rotation decisions. Currently supports Aemeath / Denia / Chisa.',
            'Team Axis Mode': 'Auto detects supported teams and falls back to the normal logic for other teams.',
            'Axis Buff Refresh Seconds': 'Refresh support/sub-DPS axis buffs when their remaining time is below this value.',
            'Custom Team Axis': 'Enable a user-defined axis script from the settings text box.',
            'Custom Axis Auto Enable File': 'Automatically enable and read custom axis files generated by Custom Axis Editor.',
            'Custom Axis Script File': 'Fallback single-axis script file generated by Custom Axis Editor.',
            'Custom Axis Profiles File': 'Multi-team axis profile library. The current 3-character team is matched automatically.',
            'Custom Axis Match Team Order': 'When true, team profiles must match the in-game team order exactly. When false, only the 3-role composition must match.',
            'Custom Axis Script': 'Multi-line custom axis script. Example: 千咲: q, r, e | when 千咲.buff<=2',
            'Custom Axis Step Timeout': 'Default timeout for one custom-axis skill action, in seconds.',
            'Custom Axis Action Retry Count': 'How many times to retry a custom-axis action when it is interrupted or fails.',
            'Custom Axis Failed Action Strategy': 'What to do after all retries fail: continue, skip step, restart axis, switch to next scripted role, or fall back to normal auto combat.',
        }
        self.config_type = {
            'Team Axis Mode': {
                'type': 'drop_down',
                'options': ['Auto', 'Aemeath-Denia-Chisa'],
            },
            'Custom Axis Failed Action Strategy': {
                'type': 'drop_down',
                'options': CUSTOM_AXIS_FAILED_ACTION_STRATEGIES,
            },
            'Custom Axis Script': {
                'type': 'text_edit',
            },
        }
        self.op_index = 0
        self.char_features_warmed_up = False
        self.custom_axis_cursor = 0
        self.custom_axis_startup_cursor = 0
        self.custom_axis_loop_cursor = 0
        self.custom_axis_startup_done = False
        self.last_custom_axis_target_enemy_time = 0
        self.custom_axis_force_start = False
        self.custom_axis_force_combat_seen = False

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
        if not self.in_combat():
            return ret
        self.custom_axis_cursor = 0
        self.custom_axis_startup_cursor = 0
        self.custom_axis_loop_cursor = 0
        self.custom_axis_startup_done = False
        while self.in_combat():
            ret = True
            try:
                current_char = self.get_current_char()
                if self._team_axis_enabled() and self._get_aemeath_denia_chisa_axis_team():
                    self.info_set('Team Axis', 'Aemeath-Denia-Chisa')
                if self._custom_axis_enabled() and self.run_custom_axis_once():
                    continue
                current_char.perform()
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {int(time.time() - self.combat_start)} {e}')
                break
        if ret:
            self.combat_end()
        return ret

    def run_custom_axis_from_f_start(self):
        self.warm_up_char_features()
        if not self.scene.in_team(self.in_team_and_world):
            return False
        if not self._custom_axis_enabled():
            self.log_error('Auto Start Axis on F triggered, but custom axis is not enabled or no axis profile matched')
            return False
        if not any(self.chars):
            if not self.load_chars():
                return False
        self.custom_axis_cursor = 0
        self.custom_axis_startup_cursor = 0
        self.custom_axis_loop_cursor = 0
        self.custom_axis_startup_done = False
        self.custom_axis_force_start = True
        self.custom_axis_force_combat_seen = False
        ret = False
        try:
            while not self._custom_axis_should_stop_for_combat():
                ret = True
                if not self.run_custom_axis_once():
                    self.next_frame()
                self._custom_axis_maybe_target_enemy()
        except (CharDeadException, NotInCombatException) as e:
            logger.info(f'custom_axis_from_f_start ended: {e}')
        finally:
            self.custom_axis_force_start = False
            if ret:
                self.combat_end()
        return ret

    def _team_axis_enabled(self):
        return bool(self.config.get('Team Axis', True))

    def _custom_axis_file_path(self):
        return Path(self.config.get('Custom Axis Script File', 'configs/custom_axis_script.txt'))

    def _custom_axis_file_exists(self):
        return self._custom_axis_file_path().exists()

    def _custom_axis_profiles_file_path(self):
        return Path(self.config.get('Custom Axis Profiles File', 'configs/custom_axis_profiles.json'))

    def _custom_axis_profiles_file_exists(self):
        return self._custom_axis_profiles_file_path().exists()

    def _custom_axis_enabled(self):
        return bool(self.config.get('Custom Team Axis', False)) or (
            bool(self.config.get('Custom Axis Auto Enable File', True)) and (
                self._custom_axis_profiles_file_exists() or self._custom_axis_file_exists()
            )
        )

    def _custom_axis_step_timeout(self):
        try:
            return float(self.config.get('Custom Axis Step Timeout', 1.2))
        except (TypeError, ValueError):
            return 1.2

    def _custom_axis_action_retry_count(self):
        try:
            return max(0, int(self.config.get('Custom Axis Action Retry Count', 1)))
        except (TypeError, ValueError):
            return 1

    def _custom_axis_retry_until_success_enabled(self):
        try:
            from src.task.CustomAxisRetryTask import CustomAxisRetryTask
            task = self.get_task_by_class(CustomAxisRetryTask)
            if task is not None:
                return bool(task.enabled)
        except Exception:
            pass
        return bool(self.config.get(CUSTOM_AXIS_RETRY_UNTIL_SUCCESS_CONFIG, False))

    def _custom_axis_global_f_enabled(self):
        try:
            from src.task.CustomAxisGlobalFTask import CustomAxisGlobalFTask
            task = self.get_task_by_class(CustomAxisGlobalFTask)
            if task is not None:
                return bool(task.enabled)
        except Exception:
            pass
        return False

    def _custom_axis_failed_action_strategy(self):
        strategy = self.config.get('Custom Axis Failed Action Strategy', 'Retry Then Continue')
        if strategy not in CUSTOM_AXIS_FAILED_ACTION_STRATEGIES:
            return 'Retry Then Continue'
        return strategy

    def _axis_refresh_threshold(self):
        try:
            return float(self.config.get('Axis Buff Refresh Seconds', 2.0))
        except (TypeError, ValueError):
            return 2.0

    def _get_aemeath_denia_chisa_axis_team(self):
        if not self._team_axis_enabled() and not self._custom_axis_enabled():
            return None
        mode = self.config.get('Team Axis Mode', 'Auto')
        if mode not in ('Auto', 'Aemeath-Denia-Chisa'):
            return None

        from src.char.Aemeath import Aemeath
        from src.char.Denia import Denia
        from src.char.Chisa import Chisa

        team = {'aemeath': None, 'denia': None, 'chisa': None}
        for char in self.chars:
            if isinstance(char, Aemeath):
                team['aemeath'] = char
            elif isinstance(char, Denia):
                team['denia'] = char
            elif isinstance(char, Chisa):
                team['chisa'] = char
        if all(team.values()):
            return team
        return None

    def _axis_buff_remaining(self, char):
        if char is None or getattr(char, 'buff_time', 0) <= 0 or not char.has_buff():
            return 0
        return max(0, char.buff_time - char.time_elapsed_accounting_for_freeze(char.last_buff_time))

    def _axis_buff_needs_refresh(self, char):
        if char is None or getattr(char, 'buff_time', 0) <= 0:
            return False
        return self._axis_buff_remaining(char) <= self._axis_refresh_threshold()

    def get_team_axis_switch_priority(self, candidate, current_char=None, has_intro=False, target_low_con=False):
        team = self._get_aemeath_denia_chisa_axis_team()
        if not team or candidate not in team.values():
            return None

        aemeath = team['aemeath']
        denia = team['denia']
        chisa = team['chisa']

        self.update_lib_portrait_icon()
        chisa_needs_buff = self._axis_buff_needs_refresh(chisa)
        denia_needs_buff = self._axis_buff_needs_refresh(denia)
        aemeath_waits_lib2 = bool(aemeath.should_wait_for_lib2())

        self.info_set('Axis Chisa Buff', round(self._axis_buff_remaining(chisa), 1))
        self.info_set('Axis Denia Buff', round(self._axis_buff_remaining(denia), 1))
        self.info_set('Axis Aemeath Lib2', round(aemeath.lib2_cooldown_left(), 1))

        if candidate is chisa:
            if aemeath_waits_lib2:
                return SwitchPriority.NO
            if chisa_needs_buff:
                return SwitchPriority.MUST
            return SwitchPriority.NO

        if candidate is denia:
            if aemeath_waits_lib2 or chisa_needs_buff:
                return SwitchPriority.NO
            if denia_needs_buff:
                return SwitchPriority.MUST
            return SwitchPriority.NORMAL

        if candidate is aemeath:
            if aemeath_waits_lib2:
                return SwitchPriority.MUST
            if chisa_needs_buff or denia_needs_buff:
                return SwitchPriority.NORMAL
            return SwitchPriority.MUST

        return None

    def _runtime_team_keys(self):
        return [char.__class__.__name__ for char in self.chars if char is not None]

    @staticmethod
    def _normalize_team_keys(team):
        keys = []
        for item in team:
            key = str(item).strip().lower()
            if key:
                keys.append(CUSTOM_AXIS_CHAR_ALIASES.get(key, key))
        return keys

    def _load_custom_axis_profiles(self):
        file_path = self._custom_axis_profiles_file_path()
        if not file_path.exists():
            return []
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except Exception as e:
            self.log_error(f'failed to read custom axis profiles file: {file_path}', e)
            return []

        if isinstance(data, dict) and isinstance(data.get('profiles'), list):
            profiles = data.get('profiles')
        elif isinstance(data, dict) and data.get('team') and data.get('steps'):
            profiles = [data]
        elif isinstance(data, list):
            profiles = data
        else:
            profiles = []

        valid_profiles = []
        for index, profile in enumerate(profiles):
            if not isinstance(profile, dict):
                continue
            team = profile.get('team') or []
            steps = profile.get('startup_steps') or profile.get('loop_steps') or profile.get('steps') or []
            if len(team) != 3 or not steps:
                self.log_debug(f'ignore invalid custom axis profile #{index}: team={team} steps={len(steps)}')
                continue
            valid_profiles.append(profile)
        return valid_profiles

    def _custom_axis_profile_matches_current_team(self, profile):
        runtime_team = self._normalize_team_keys(self._runtime_team_keys())
        profile_team = self._normalize_team_keys(profile.get('team') or [])
        if len(runtime_team) != 3 or len(profile_team) != 3:
            return False
        if self.config.get('Custom Axis Match Team Order', False):
            return runtime_team == profile_team
        return sorted(runtime_team) == sorted(profile_team)

    def _active_custom_axis_profile(self):
        profiles = self._load_custom_axis_profiles()
        if not profiles:
            return None
        runtime_team = self._runtime_team_keys()
        for profile in profiles:
            if self._custom_axis_profile_matches_current_team(profile):
                profile_name = profile.get('name') or ' / '.join(profile.get('team') or [])
                self.info_set('Custom Axis Profile', profile_name)
                self.log_debug(f'custom axis matched profile {profile_name} for team {runtime_team}')
                return profile
        self.info_set('Custom Axis Profile', f'No Match: {runtime_team}')
        return None

    @staticmethod
    def _profile_action_to_text(action):
        if isinstance(action, str):
            return action
        if isinstance(action, dict):
            name = action.get('name') or action.get('action') or ''
            value = action.get('value')
            if value is None or value == '':
                return str(name)
            return f'{name}:{value}'
        return str(action)

    def _profile_steps_to_axis_lines(self, profile, section_key='loop_steps'):
        axis_lines = []
        raw_steps = profile.get(section_key)
        if raw_steps is None and section_key == 'loop_steps':
            raw_steps = profile.get('steps') or []
        for step in raw_steps or []:
            if isinstance(step, str):
                parsed = self._parse_custom_axis_line(step)
                if parsed:
                    axis_lines.append(parsed)
                continue
            if not isinstance(step, dict):
                continue
            role = step.get('role') or step.get('char') or step.get('character')
            actions = [self._profile_action_to_text(action) for action in (step.get('actions') or [])]
            fallback_actions = [
                self._profile_action_to_text(action) for action in (step.get('fallback_actions') or [])
            ]
            fallback_role = step.get('fallback_role') or step.get('fallback_char') or role
            condition = step.get('condition') or ''
            if not role or not actions:
                continue
            raw = f"{role}: {', '.join(actions)}"
            if condition:
                raw += f" | 条件 {condition}"
            if fallback_actions:
                raw += f" | 未满足 {fallback_role}: {', '.join(fallback_actions)}"
            axis_lines.append({
                'char': str(role).strip(),
                'actions': [action for action in actions if action],
                'condition': str(condition).strip(),
                'fallback_actions': [action for action in fallback_actions if action],
                'fallback_char': str(fallback_role).strip(),
                'raw': raw,
            })
        return axis_lines

    def _profile_to_axis_sections(self, profile):
        return {
            'startup': self._profile_steps_to_axis_lines(profile, 'startup_steps'),
            'loop': self._profile_steps_to_axis_lines(profile, 'loop_steps'),
        }

    def _custom_axis_script(self):
        if self.config.get('Custom Axis Auto Enable File', True):
            file_path = self._custom_axis_file_path()
            if file_path.exists():
                try:
                    return file_path.read_text(encoding='utf-8')
                except Exception as e:
                    self.log_error(f'failed to read custom axis script file: {file_path}', e)
        return self.config.get('Custom Axis Script') or ''

    def _custom_axis_sections_from_script(self):
        sections = {'startup': [], 'loop': []}
        current_section = 'loop'
        for raw_line in self._custom_axis_script().splitlines():
            stripped = raw_line.strip()
            lowered = stripped.lower()
            if stripped.startswith('#'):
                if '启动轴' in stripped or 'start' in lowered or 'startup' in lowered:
                    current_section = 'startup'
                elif '循环轴' in stripped or 'loop' in lowered:
                    current_section = 'loop'
                continue
            parsed = self._parse_custom_axis_line(raw_line)
            if parsed:
                sections[current_section].append(parsed)
        return sections

    def _custom_axis_sections(self):
        profile = self._active_custom_axis_profile()
        if profile:
            sections = self._profile_to_axis_sections(profile)
            if sections['startup'] or sections['loop']:
                return sections
        return self._custom_axis_sections_from_script()

    def _custom_axis_lines(self):
        sections = self._custom_axis_sections()
        return sections['startup'] + sections['loop']

    def _parse_custom_axis_line(self, raw_line):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            return None

        condition = ''
        fallback_actions = []
        fallback_char = ''
        if '|' in line:
            chunks = [chunk.strip() for chunk in line.split('|')]
            line = chunks[0]
            for chunk in chunks[1:]:
                if chunk.startswith(('未满足', '否则', '不满足', '条件未满足')) or chunk.lower().startswith('fallback '):
                    fallback_text = self._strip_axis_fallback_prefix(chunk)
                    if ':' in fallback_text:
                        maybe_char, maybe_actions = fallback_text.split(':', 1)
                        if maybe_char.strip().lower() not in CUSTOM_AXIS_ACTION_NAMES:
                            fallback_char, fallback_text = maybe_char.strip(), maybe_actions
                    fallback_actions = [part.strip() for part in re.split(r'[,，;；]', fallback_text) if part.strip()]
                else:
                    condition = self._strip_axis_condition_prefix(chunk)

        if ':' not in line:
            return None

        char_name, actions_text = line.split(':', 1)
        actions = [part.strip() for part in re.split(r'[,，;；]', actions_text) if part.strip()]
        if not actions:
            return None
        return {
            'char': char_name.strip(),
            'actions': actions,
            'condition': condition,
            'fallback_actions': fallback_actions,
            'fallback_char': fallback_char,
            'raw': raw_line,
        }

    def run_custom_axis_once(self):
        self._custom_axis_maybe_target_enemy()
        sections = self._custom_axis_sections()
        startup_lines = sections['startup']
        loop_lines = sections['loop']
        if not startup_lines and not loop_lines:
            self.log_error('Custom Team Axis is enabled, but no custom axis profile/script matched the current team')
            return False

        if startup_lines and not self.custom_axis_startup_done:
            axis_line = self._next_custom_axis_line(startup_lines, 'custom_axis_startup_cursor', loop=False)
            if axis_line:
                self.info_set('Custom Axis Phase', '启动轴')
                return self._execute_custom_axis_line(axis_line)
            self.custom_axis_startup_done = True
            self.custom_axis_loop_cursor = 0

        if not loop_lines:
            self.log_debug('custom axis startup finished and no loop axis configured')
            self.next_frame()
            return True

        axis_line = self._next_custom_axis_line(loop_lines, 'custom_axis_loop_cursor', loop=True)
        if axis_line:
            self.info_set('Custom Axis Phase', '循环轴')
            return self._execute_custom_axis_line(axis_line)

        self.log_debug('custom axis skipped: no condition matched')
        self.next_frame()
        return True

    def _next_custom_axis_line(self, axis_lines, cursor_attr, loop=True):
        if not axis_lines:
            return None
        cursor = getattr(self, cursor_attr, 0)
        if loop and cursor >= len(axis_lines):
            cursor = 0
        if not loop and cursor >= len(axis_lines):
            return None

        count = len(axis_lines) if loop else len(axis_lines) - cursor
        for offset in range(count):
            line_index = (cursor + offset) % len(axis_lines) if loop else cursor + offset
            axis_line = axis_lines[line_index]
            if not self._axis_condition_met(axis_line.get('condition')):
                fallback_actions = axis_line.get('fallback_actions') or []
                if offset == 0 and fallback_actions:
                    fallback_line = dict(axis_line)
                    fallback_line['actions'] = fallback_actions
                    fallback_line['char'] = axis_line.get('fallback_char') or axis_line.get('char')
                    fallback_line['condition_failed_fallback'] = True
                    fallback_line['raw'] = f"{axis_line.get('raw', '').strip()} [条件未满足，小循环]"
                    return fallback_line
                continue
            next_cursor = line_index + 1
            if loop:
                next_cursor %= len(axis_lines)
            setattr(self, cursor_attr, next_cursor)
            self.custom_axis_cursor = next_cursor
            return axis_line
        if not loop:
            setattr(self, cursor_attr, len(axis_lines))
        return None

    def _execute_custom_axis_line(self, axis_line):
        target = self._find_axis_char(axis_line['char'])
        if target is None:
            self.log_error(f"custom axis target not found: {axis_line['char']}")
            return False
        if not self._switch_to_axis_char(target):
            return False

        self.info_set('Custom Axis', axis_line['raw'].strip())
        f_monitor_enabled = self._custom_axis_global_f_enabled()
        for action in axis_line['actions']:
            if self._custom_axis_should_stop_for_combat():
                return True
            if self._custom_axis_should_interrupt_condition_fallback(axis_line):
                self.log_debug(f"custom axis fallback interrupted because condition is met: {axis_line.get('raw', '')}")
                return True
            self._custom_axis_maybe_target_enemy()
            if self._custom_axis_is_f_monitor_action(action):
                f_monitor_enabled = True
                self.log_debug(f'custom axis enable F monitor for current step: {target}.{action}')
                continue
            if f_monitor_enabled and not self._custom_axis_is_f_once_action(action):
                self._custom_axis_safe_f_break(target, check_f_on_switch=False)
            if self._execute_custom_axis_line_action(target, action, axis_line):
                if f_monitor_enabled and not self._custom_axis_is_f_once_action(action):
                    self._custom_axis_safe_f_break(target, check_f_on_switch=False)
                if self._custom_axis_should_interrupt_condition_fallback(axis_line):
                    self.next_frame()
                    return True
                self.next_frame()
                continue

            strategy = self._custom_axis_failed_action_strategy()
            self.log_error(f'custom axis action failed after retry: {target}.{action}, strategy={strategy}')
            if strategy == 'Retry Then Continue':
                self.next_frame()
                continue
            if strategy == 'Retry Then Skip Step':
                return True
            if strategy == 'Retry Then Restart Axis':
                self.custom_axis_cursor = 0
                self.custom_axis_startup_cursor = 0
                self.custom_axis_loop_cursor = 0
                self.custom_axis_startup_done = False
                return True
            if strategy == 'Retry Then Switch Next Script Role':
                self._switch_to_next_axis_role(target)
                return True
            if strategy == 'Retry Then Fallback Normal Combat':
                return False
        return True

    def _execute_custom_axis_line_action(self, target, action, axis_line):
        if self._custom_axis_should_interrupt_condition_fallback(axis_line):
            return True
        condition = axis_line.get('condition')
        is_fallback = bool(axis_line.get('condition_failed_fallback'))
        if self._custom_axis_is_attack_until_condition_action(action):
            return self._execute_custom_axis_attack_until_condition(
                target,
                action,
                condition,
                fail_on_timeout=not is_fallback,
            )
        if is_fallback and self._custom_axis_is_basic_attack_action(action):
            return self._execute_custom_axis_attack_until_condition(
                target,
                action,
                condition,
                fail_on_timeout=False,
            )
        if is_fallback and self._custom_axis_is_wait_action(action):
            return self._execute_custom_axis_wait_until_condition(
                action,
                condition,
            )
        if self._custom_axis_is_heavy_until_condition_action(action):
            return self._execute_custom_axis_heavy_until_condition(
                target,
                action,
                condition,
            )
        return self._execute_custom_axis_action_with_retry(target, action)

    def _get_current_axis_char(self):
        try:
            return self.get_current_char(raise_exception=False)
        except TypeError:
            try:
                return self.get_current_char()
            except Exception:
                return None
        except Exception:
            return None

    def _custom_axis_switch_timeout(self):
        return getattr(self, 'switch_char_time_out', 10) or 10

    def _custom_axis_safe_f_break(self, char, check_f_on_switch=True):
        if char is None:
            return
        if check_f_on_switch and not getattr(char, 'check_f_on_switch', True):
            return
        if not hasattr(char, 'f_break'):
            return
        try:
            char.f_break(check_f_on_switch=check_f_on_switch)
        except TypeError:
            char.f_break()
        except Exception as e:
            self.log_debug(f'custom axis f_break skipped: {e}')

    def _custom_axis_is_f_monitor_action(self, action):
        name, _ = self._parse_custom_axis_action(action)
        return name in {'f_until', 'f_auto', 'f_loop', '持续交互', '持续f'}

    def _custom_axis_is_f_once_action(self, action):
        name, _ = self._parse_custom_axis_action(action)
        return name in {'f', 'break', 'f_break', '交互'}

    def _custom_axis_should_interrupt_condition_fallback(self, axis_line):
        return bool(
            axis_line.get('condition_failed_fallback')
            and axis_line.get('condition')
            and self._axis_condition_met(axis_line.get('condition'))
        )

    def _custom_axis_is_basic_attack_action(self, action):
        name, _ = self._parse_custom_axis_action(action)
        return name in {'attack', 'click', 'a', 'normal', '普攻', '平a'}

    def _custom_axis_is_attack_until_condition_action(self, action):
        name, _ = self._parse_custom_axis_action(action)
        return name in {'attack_until_condition', 'normal_until_condition', '普攻到条件满足', '平a到条件满足'}

    def _custom_axis_is_wait_action(self, action):
        name, _ = self._parse_custom_axis_action(action)
        return name in {'wait', 'sleep', '等待'}

    def _custom_axis_is_heavy_until_condition_action(self, action):
        name, _ = self._parse_custom_axis_action(action)
        return name in {'heavy_until_condition', '重击到条件满足'}

    @staticmethod
    def _custom_axis_is_timed_resonance_action(name, value):
        return value is not None or name in {'e_wait', 'skill_wait', '技能等待'}

    @staticmethod
    def _custom_axis_is_animated_resonance_action(name):
        return name in CUSTOM_AXIS_ANIMATED_RESONANCE_ACTION_NAMES

    def _custom_axis_should_stop_for_combat(self):
        in_combat = bool(self.in_combat())
        if in_combat:
            self.custom_axis_force_combat_seen = True
            return False
        if getattr(self, 'custom_axis_force_start', False):
            return bool(getattr(self, 'custom_axis_force_combat_seen', False))
        return True

    def _custom_axis_maybe_target_enemy(self):
        if not self.config.get('Auto Target', True):
            return
        now = time.time()
        if now - getattr(self, 'last_custom_axis_target_enemy_time', 0) < CUSTOM_AXIS_TARGET_ENEMY_INTERVAL:
            return
        self.last_custom_axis_target_enemy_time = now
        try:
            self.target_enemy(wait=False)
        except Exception as e:
            logger.debug(f'custom axis target enemy skipped: {e}')

    def _execute_custom_axis_timed_resonance(self, char, action, value, start_time):
        custom_resonance_available = getattr(char, 'custom_axis_resonance_available', None)
        resonance_available = (
            custom_resonance_available()
            if callable(custom_resonance_available)
            else char.resonance_available()
        )
        if not resonance_available:
            self.log_debug(f'custom axis timed resonance not available: {char}.{action}')
            return False

        try:
            enhance_e_available = getattr(char, 'enhance_e_available', None)
            enhance_e_clicked = bool(enhance_e_available()) if callable(enhance_e_available) else False
        except Exception:
            enhance_e_clicked = False

        if hasattr(char, 'record_resonance_use'):
            char.record_resonance_use()
        if enhance_e_clicked and hasattr(char, 'record_enhance_e'):
            char.record_enhance_e()

        if hasattr(char, 'send_resonance_key'):
            char.send_resonance_key()
        else:
            self.send_key(char.get_resonance_key())

        self._custom_axis_wait_after_action(value if value is not None else 0.05)
        return self._custom_axis_after_action_ok(char, action, start_time)

    def _execute_custom_axis_animated_resonance(self, char, action, value, start_time, timeout):
        custom_resonance_available = getattr(char, 'custom_axis_resonance_available', None)
        resonance_available = (
            custom_resonance_available()
            if callable(custom_resonance_available)
            else char.resonance_available()
        )
        if not resonance_available:
            self.log_debug(f'custom axis animated resonance not available: {char}.{action}')
            return False

        custom_resonance = getattr(char, 'custom_axis_resonance', None)
        if callable(custom_resonance):
            clicked = custom_resonance(timeout=timeout)
        else:
            clicked, _, _ = char.click_resonance(
                has_animation=True,
                send_click=False,
                animation_min_duration=0,
                time_out=timeout,
            )
        if not clicked:
            return False
        self._custom_axis_wait_after_action(value)
        return self._custom_axis_after_action_ok(char, action, start_time)

    def _custom_axis_wait_after_action(self, value):
        if value is None or value <= 0:
            return
        self._custom_axis_maybe_target_enemy()
        self.sleep(value)

    def _execute_custom_axis_attack_until_condition(self, char, action, condition, fail_on_timeout=True):
        name, value = self._parse_custom_axis_action(action)
        duration = value if value is not None else 3.0
        start = time.time()
        condition = (condition or '').strip()
        if not condition:
            return self._execute_custom_axis_action_with_retry(char, f'attack:{duration}')
        while time.time() - start < duration:
            if self._axis_condition_met(condition):
                return self._custom_axis_after_action_ok(char, action, start)
            self.click()
            remaining = duration - (time.time() - start)
            if remaining > 0:
                self.sleep(min(0.01, remaining))
            self.next_frame()
        if not self._axis_condition_met(condition) and fail_on_timeout:
            self.log_debug(f'custom axis {name} timed out before condition met: {char}.{condition}')
            return False
        return self._custom_axis_after_action_ok(char, action, start)

    def _execute_custom_axis_wait_until_condition(self, action, condition):
        _, value = self._parse_custom_axis_action(action)
        duration = value if value is not None else 0.2
        start = time.time()
        condition = (condition or '').strip()
        while time.time() - start < duration:
            if condition and self._axis_condition_met(condition):
                break
            remaining = duration - (time.time() - start)
            if remaining > 0:
                self.sleep(min(0.01, remaining))
            self.next_frame()
        return True

    def _execute_custom_axis_heavy_until_condition(self, char, action, condition):
        name, value = self._parse_custom_axis_action(action)
        if name not in {'heavy_until_condition', '重击到条件满足'}:
            return self._execute_custom_axis_action_with_retry(char, action)
        duration = value if value is not None else 3.0
        start = time.time()
        condition = (condition or '').strip()
        if not condition:
            return self._execute_custom_axis_action_with_retry(char, f'heavy:{duration}')
        custom_heavy_until_condition = getattr(char, 'custom_axis_heavy_until_condition', None)
        if callable(custom_heavy_until_condition):
            clicked = custom_heavy_until_condition(duration, lambda: self._axis_condition_met(condition))
            return bool(clicked) and self._custom_axis_after_action_ok(char, action, start)
        try:
            self.mouse_down()
            while time.time() - start < duration:
                if self._axis_condition_met(condition):
                    break
                try:
                    char.check_target(True)
                except Exception:
                    pass
                self.next_frame()
        finally:
            self.mouse_up()
            self.sleep(0.01)
        if not self._axis_condition_met(condition):
            self.log_debug(f'custom axis heavy_until_condition timed out before condition met: {char}.{condition}')
            return False
        return self._custom_axis_after_action_ok(char, action, start)

    def _complete_custom_axis_switch(self, current_char, target, has_intro, start_time):
        self.in_liberation = False
        for char in self.chars:
            if char is not None:
                char.is_current_char = char == target

        if current_char is not None and current_char != target:
            if not has_intro:
                self._custom_axis_safe_f_break(current_char, check_f_on_switch=True)
            current_char.switch_out(con_full=has_intro)

        target.has_intro = has_intro
        target.has_sub_dps_intro = bool(has_intro and current_char and current_char.is_sub_dps)
        target.last_switch_in_time = time.time()
        custom_axis_on_switch_in = getattr(target, 'custom_axis_on_switch_in', None)
        if callable(custom_axis_on_switch_in):
            custom_axis_on_switch_in(current_char=current_char, has_intro=has_intro)
        if has_intro:
            current_time = time.time()
            self.add_freeze_duration(current_time, target.intro_motion_freeze_duration, -100)
            if current_char is not None:
                current_char.last_outro_time = current_time

        self.log_info(
            f'custom axis switch end {current_char}->{target} '
            f'has_intro {target.has_intro} has_sub_dps_intro {target.has_sub_dps_intro} '
            f'{time.time() - start_time:.3f}s'
        )
        return True

    def _switch_to_axis_char(self, target):
        """Switch to a custom-axis target with checks close to BaseCombatTask.switch_next_char."""
        self.update_lib_portrait_icon()
        in_team, current_index, _ = self.in_team()
        if not in_team:
            self.raise_not_in_combat('custom axis switch not in team before switching')

        current_char = self._get_current_axis_char()
        if current_char is None and 0 <= current_index < len(self.chars):
            current_char = self.chars[current_index]

        has_intro = False
        current_con = 0
        if current_char is not None and current_char != target:
            try:
                current_con = current_char.get_current_con()
                if current_con > 0.8 and current_con != 1:
                    self.log_debug(f'custom axis current_con {current_con:.2f} almost full, recheck')
                    self.sleep(0.05)
                    self.next_frame()
                    current_con = current_char.get_current_con()
                has_intro = current_con == 1
            except Exception as e:
                self.log_debug(f'custom axis failed to read concerto before switch: {e}')

        start = time.time()
        if current_index == target.index:
            self.in_liberation = False
            for char in self.chars:
                if char is not None:
                    char.is_current_char = char == target
            self.log_info(f'custom axis already on {target} {time.time() - start:.3f}s')
            return True

        last_click = 0
        switch_timeout = self._custom_axis_switch_timeout()
        while True:
            now = time.time()
            in_team, current_index, _ = self.in_team()
            if not in_team:
                logger.info(f'not in team while custom-axis switching {current_char}_to_{target} {now - start}')
                if now - start > switch_timeout:
                    self.raise_not_in_combat(
                        f'custom axis switch too long not in_team {current_char}_to_{target}, {now - start}')
                self.next_frame()
                continue

            if current_index == target.index:
                return self._complete_custom_axis_switch(current_char, target, has_intro, start)

            if current_char is not None and current_index == current_char.index:
                self.update_lib_portrait_icon()
                try:
                    refreshed_has_intro = has_intro or current_char.is_con_full()
                except Exception:
                    refreshed_has_intro = has_intro
                if refreshed_has_intro != has_intro:
                    has_intro = refreshed_has_intro
                    self.log_info(f'custom axis intro became available while switching to {target}')
                if has_intro:
                    self._custom_axis_safe_f_break(current_char, check_f_on_switch=True)

            if now - last_click > 0.1:
                self.send_key(target.index + 1)
                self.sleep(0.001)
                self.log_debug(f'custom axis switch not detected, send {target.index + 1}')
                last_click = now

            if now - start > switch_timeout:
                if self.debug:
                    self.screenshot(f'custom_axis_switch_failed_{current_char}_to_{target}')
                self.raise_not_in_combat(
                    f'custom axis failed switch chars {current_char}_to_{target}, {now - start}')
            self.next_frame()

    def _switch_to_next_axis_role(self, current_target):
        sections = self._custom_axis_sections()
        axis_lines = sections['loop'] or sections['startup']
        if not axis_lines:
            return False
        for offset in range(len(axis_lines)):
            cursor = self.custom_axis_loop_cursor if sections['loop'] else self.custom_axis_startup_cursor
            line_index = (cursor + offset) % len(axis_lines)
            axis_line = axis_lines[line_index]
            if not self._axis_condition_met(axis_line.get('condition')):
                continue
            target = self._find_axis_char(axis_line['char'])
            if target is not None and target != current_target:
                next_cursor = (line_index + 1) % len(axis_lines)
                if sections['loop']:
                    self.custom_axis_loop_cursor = next_cursor
                else:
                    self.custom_axis_startup_cursor = next_cursor
                self.custom_axis_cursor = next_cursor
                return self._switch_to_axis_char(target)
        return False

    def _custom_axis_after_action_ok(self, char, action, start_time):
        if self._custom_axis_should_stop_for_combat():
            self.log_info(f'custom axis action ended because combat finished: {char}.{action}')
            return True
        in_team, current_index, _ = self.in_team()
        if not in_team:
            self.log_error(f'custom axis action interrupted, not in team: {char}.{action}')
            return False
        if char is not None and current_index != char.index:
            self.log_error(
                f'custom axis action interrupted, current char changed: {char}.{action} -> index {current_index}')
            return False
        elapsed = time.time() - start_time
        self.log_debug(f'custom axis action ok: {char}.{action} {elapsed:.2f}s')
        return True

    def _execute_custom_axis_action_with_retry(self, char, action):
        if self._custom_axis_retry_until_success_enabled():
            return self._execute_custom_axis_action_until_success(char, action)

        retry_count = self._custom_axis_action_retry_count()
        for attempt in range(retry_count + 1):
            if attempt > 0:
                self.log_info(f'custom axis retry action {attempt}/{retry_count}: {char}.{action}')
                if not self._switch_to_axis_char(char):
                    return False
                self.sleep(0.1)
            if self._execute_custom_axis_action(char, action):
                return True
        return False

    def _execute_custom_axis_action_until_success(self, char, action):
        attempt = 0
        while True:
            if self._custom_axis_should_stop_for_combat():
                return True
            if attempt > 0:
                if attempt == 1 or attempt % 20 == 0:
                    self.log_info(f'custom axis retry action until success {attempt}: {char}.{action}')
                if not self._switch_to_axis_char(char):
                    return False
            if self._execute_custom_axis_action(char, action):
                return True
            attempt += 1
            if self._custom_axis_should_stop_for_combat():
                return True
            self.sleep(CUSTOM_AXIS_ACTION_RETRY_INTERVAL)
            self.next_frame()

    def _execute_custom_axis_action(self, char, action):
        name, value = self._parse_custom_axis_action(action)
        timeout = self._custom_axis_step_timeout()
        start = time.time()

        if name in CUSTOM_AXIS_ROLE_FLOW_ACTION_NAMES:
            return self._execute_custom_axis_role_flow(char, action, start)
        elif name in {'e', 'e_wait', 'e_anim', 'e_animation', 'res', 'resonance', 'res_anim', 'resonance_anim',
                      'skill', 'skill_wait', 'skill_anim', '共鸣', '共鸣技能', '技能', '技能等待'}:
            if self._custom_axis_is_animated_resonance_action(name):
                return self._execute_custom_axis_animated_resonance(char, action, value, start, timeout)
            if self._custom_axis_is_timed_resonance_action(name, value):
                return self._execute_custom_axis_timed_resonance(char, action, value, start)
            custom_resonance_available = getattr(char, 'custom_axis_resonance_available', None)
            resonance_available = (
                custom_resonance_available()
                if callable(custom_resonance_available)
                else char.resonance_available()
            )
            if not resonance_available:
                self.log_debug(f'custom axis resonance not available: {char}.{action}')
                return False
            custom_resonance = getattr(char, 'custom_axis_resonance', None)
            if callable(custom_resonance):
                clicked = custom_resonance(timeout=timeout)
            else:
                clicked, _, _ = char.click_resonance(time_out=timeout, send_click=False)
            return bool(clicked) and self._custom_axis_after_action_ok(char, action, start)
        elif name in {'r', 'lib', 'liberation', 'ult', '大招', '解放', '共鸣解放'}:
            custom_liberation = getattr(char, 'custom_axis_liberation', None)
            if callable(custom_liberation):
                clicked = custom_liberation()
                if not clicked:
                    return False
                self._custom_axis_wait_after_action(value)
                return self._custom_axis_after_action_ok(char, action, start)
            if not char.liberation_available():
                self.log_debug(f'custom axis liberation not available: {char}.{action}')
                return False
            clicked = char.click_liberation(wait_if_cd_ready=0)
            if not clicked:
                return False
            self._custom_axis_wait_after_action(value)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'q', 'echo', '声骸'}:
            if not char.echo_available():
                self.log_debug(f'custom axis echo not available: {char}.{action}')
                return False
            clicked = char.click_echo(time_out=0)
            if not clicked:
                return False
            self._custom_axis_wait_after_action(value)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'attack', 'click', 'a', 'normal', '普攻', '平a'}:
            char.continues_normal_attack(value if value is not None else 0.5, interval=0.01)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'attack_until_con', 'attack_until_con_full', 'normal_until_con', '普攻到协奏满', '平a到协奏满'}:
            char.continues_normal_attack(value if value is not None else 6.0, interval=0.01, until_con_full=True)
            try:
                con_full = char.is_con_full()
            except Exception:
                con_full = getattr(char, 'current_con', 0) == 1
            if not con_full:
                self.log_debug(f'custom axis attack_until_con timed out before concerto full: {char}.{action}')
                return False
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'heavy', 'heavy_attack', '重击'}:
            custom_heavy = getattr(char, 'custom_axis_heavy_attack', None)
            if callable(custom_heavy):
                result = custom_heavy(value)
                if result is False:
                    return False
            else:
                char.heavy_attack(value if value is not None else 0.6)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'heavy_until_con', 'heavy_until_con_full', '重击到协奏满'}:
            duration = value if value is not None else 6.0
            custom_heavy_until_con = getattr(char, 'custom_axis_heavy_until_con', None)
            if callable(custom_heavy_until_con):
                clicked = custom_heavy_until_con(duration)
                return bool(clicked) and self._custom_axis_after_action_ok(char, action, start)
            else:
                try:
                    char.heavy_attack(duration, until_con_full=True)
                except TypeError:
                    custom_heavy = getattr(char, 'custom_axis_heavy_attack', None)
                    if callable(custom_heavy):
                        custom_heavy(duration)
                    else:
                        char.heavy_attack(duration)
            try:
                con_full = char.is_con_full()
            except Exception:
                con_full = getattr(char, 'current_con', 0) == 1
            if not con_full:
                self.log_debug(f'custom axis heavy_until_con timed out before concerto full: {char}.{action}')
                return False
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'dodge', 'dash', 'evade', '闪避'}:
            char.continues_right_click(value if value is not None else 0.05)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'jump', 'space', '跳起', '跳跃'}:
            self.jump(after_sleep=value if value is not None else 0.05)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'wait', 'sleep', '等待'}:
            self.sleep(value if value is not None else 0.2)
            return self._custom_axis_after_action_ok(char, action, start)
        elif name in {'f', 'break', 'f_break', '交互'}:
            if hasattr(char, 'f_break'):
                self._custom_axis_safe_f_break(char, check_f_on_switch=False)
                self._custom_axis_wait_after_action(value)
                return self._custom_axis_after_action_ok(char, action, start)
            return False
        elif name in {'f_until', 'f_auto', 'f_loop', '持续交互', '持续f'}:
            self.log_debug(f'custom axis F monitor marker skipped outside step executor: {char}.{action}')
            return True
        else:
            self.log_error(f'unknown custom axis action: {action}')
            return False

    def _execute_custom_axis_role_flow(self, char, action, start_time):
        role_flow = getattr(char, 'custom_axis_role_flow', None)
        if not callable(role_flow):
            self.log_debug(f'custom axis role flow not supported, skip: {char}.{action}')
            return True
        completed = role_flow()
        return completed is not False and self._custom_axis_after_action_ok(char, action, start_time)

    @staticmethod
    def _parse_custom_axis_action(action):
        action = action.strip()
        if ':' in action:
            name, value = action.split(':', 1)
        else:
            name, value = action, None
        try:
            value = float(value) if value is not None and value.strip() != '' else None
        except ValueError:
            value = None
        return name.strip().lower(), value

    def _axis_condition_met(self, condition):
        if not condition:
            return True
        condition = self._strip_axis_condition_prefix(condition)
        parts = [part.strip() for part in re.split(r'\s*(?:&&|and|且|,|，)\s*', condition) if part.strip()]
        return all(self._eval_axis_condition_part(part) for part in parts)

    @staticmethod
    def _strip_axis_condition_prefix(condition):
        condition = str(condition).strip()
        lowered = condition.lower()
        if lowered.startswith('when '):
            return condition[5:].strip()
        for prefix in ('条件', '当', '满足'):
            if condition.startswith(prefix):
                return condition[len(prefix):].lstrip(' :：').strip()
        return condition

    @staticmethod
    def _strip_axis_fallback_prefix(text):
        text = str(text).strip()
        lowered = text.lower()
        if lowered.startswith('fallback '):
            return text[9:].strip()
        for prefix in ('未满足', '否则', '不满足', '条件未满足'):
            if text.startswith(prefix):
                return text[len(prefix):].lstrip(' :：').strip()
        return text

    def _eval_axis_condition_part(self, part):
        negate = False
        part = part.strip()
        if part.startswith('!'):
            negate = True
            part = part[1:].strip()
        elif part.lower().startswith('not '):
            negate = True
            part = part[4:].strip()

        match = re.match(r'^([\w\u4e00-\u9fff]+)\.([\w\u4e00-\u9fff]+)\s*(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)$', part)
        if match:
            char_name, state_name, op, expected_text = match.groups()
            current = self._axis_state_value(char_name, state_name)
            expected = float(expected_text)
            result = self._compare_axis_value(current, op, expected)
            return not result if negate else result

        match = re.match(r'^([\w\u4e00-\u9fff]+)\.([\w\u4e00-\u9fff]+)$', part)
        if match:
            char_name, state_name = match.groups()
            result = bool(self._axis_state_value(char_name, state_name))
            return not result if negate else result

        self.log_error(f'invalid custom axis condition: {part}')
        return False

    @staticmethod
    def _compare_axis_value(current, op, expected):
        if op == '<=':
            return current <= expected
        if op == '>=':
            return current >= expected
        if op == '<':
            return current < expected
        if op == '>':
            return current > expected
        if op == '==':
            return current == expected
        if op == '!=':
            return current != expected
        return False

    def _axis_state_value(self, char_name, state_name):
        char = self._find_axis_char(char_name)
        if char is None:
            return 0

        state = state_name.lower()
        self.update_lib_portrait_icon()
        custom_axis_state_value = getattr(char, 'custom_axis_state_value', None)
        if callable(custom_axis_state_value):
            custom_value = custom_axis_state_value(state)
            if custom_value is not None:
                return custom_value
        if state in {'buff', 'buff_remaining', 'buff剩余', '增益', '增益剩余'}:
            return self._axis_buff_remaining(char)
        if state in {'has_buff', 'buff_active', '有buff', '有增益'}:
            return 1 if char.has_buff() else 0
        if state in {'buff_time', 'buff_total', 'buff_duration', 'buff时长', '增益时长'}:
            return getattr(char, 'buff_time', 0)
        if state in {'buff_elapsed', 'buff_used', 'buff已过', '增益已过'}:
            last_buff_time = getattr(char, 'last_buff_time', -1)
            if last_buff_time < 0:
                return 10000
            return char.time_elapsed_accounting_for_freeze(last_buff_time)
        if state in {'lib2', 'lib2_cd', '二段大', '二段大招'} and hasattr(char, 'lib2_cooldown_left'):
            return char.lib2_cooldown_left()
        if state in {'lib2_ready', '二段大可用'} and hasattr(char, 'lib2_available'):
            return 1 if char.lib2_available() else 0
        if state in {'wait_lib2', '等二段大'} and hasattr(char, 'should_wait_for_lib2'):
            return 1 if char.should_wait_for_lib2() else 0
        if state in {'con', 'concerto', '协奏'}:
            try:
                return char.get_current_con()
            except Exception:
                return getattr(char, 'current_con', 0)
        if state in {'con_full', '协奏满'}:
            try:
                return 1 if char.is_con_full() else 0
            except Exception:
                return 1 if getattr(char, 'current_con', 0) == 1 else 0
        if state in {'lib', 'liberation', 'r', 'ult', '大招', '解放', '共鸣解放'}:
            return 1 if char.liberation_available() else 0
        if state in {'res', 'resonance', 'e', 'skill', '共鸣', '共鸣技能', '技能'}:
            custom_resonance_available = getattr(char, 'custom_axis_resonance_available', None)
            if callable(custom_resonance_available):
                return 1 if custom_resonance_available() else 0
            return 1 if char.resonance_available() else 0
        if state in {'echo', 'q', '声骸'}:
            return 1 if char.echo_available() else 0
        if state in {'extra', 'extra_action', '额外技能'}:
            return 1 if char.extra_action_available() else 0
        if state in {'res_cd', 'e_cd', '共鸣冷却'}:
            return 1 if char.has_cd('resonance') else 0
        if state in {'echo_cd', 'q_cd', '声骸冷却'}:
            return 1 if char.has_cd('echo') else 0
        if state in {'lib_cd', 'r_cd', '解放冷却'}:
            return 1 if char.has_cd('liberation') else 0
        if state in {'forte', 'forte_full', '回路', '协奏回路'}:
            return 1 if char.is_forte_full() else 0
        if state in {'current', '当前'}:
            return 1 if char.is_current_char else 0
        return 0

    def _find_axis_char(self, char_name):
        key = str(char_name).strip().lower()
        if key.isdigit():
            index = int(key) - 1
            if 0 <= index < len(self.chars):
                return self.chars[index]
            return None

        wanted = CUSTOM_AXIS_CHAR_ALIASES.get(key, key)
        team = self._get_aemeath_denia_chisa_axis_team()
        if team and wanted in team:
            return team[wanted]

        for char in self.chars:
            if char is None:
                continue
            class_key = char.__class__.__name__.lower()
            names = {
                class_key,
                str(getattr(char, 'char_name', '')).lower(),
                str(char).lower(),
            }
            if key in names or wanted == class_key:
                return char
        return None

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
