import time
from dataclasses import dataclass


class CustomRotationConfigError(ValueError):
    pass


@dataclass
class RotationAction:
    line_no: int
    raw: str
    name: str
    value: str | None = None
    interval: float | None = None


class CustomRotation:
    DEFAULT_TAP_INTERVAL = 0.1
    DEFAULT_HEAVY_DURATION = 0.6
    DEFAULT_KEY_AFTER_SLEEP = 0.01

    def __init__(self, task):
        self.task = task
        self._script = None
        self._actions = []
        self._index = 0

    def load(self, script, reset=False):
        script = script or ''
        if script != self._script:
            self._script = script
            self._actions = self._parse(script)
            self._index = 0
        elif reset:
            self._index = 0
        if not self._actions:
            raise CustomRotationConfigError('自定义技能轴没有有效动作')

    def perform_next(self):
        if not self._actions:
            raise CustomRotationConfigError('自定义技能轴没有有效动作')
        action = self._actions[self._index]
        self._index = (self._index + 1) % len(self._actions)
        self.task.log_info(f'自定义技能轴 第{action.line_no}行: {action.raw}')
        self._perform(action)

    def _perform(self, action):
        current_char = self.task.get_current_char(raise_exception=True)
        name = action.name
        if name == 'switch':
            if action.value is None:
                current_char.switch_next_char()
            else:
                self._switch_to(int(action.value))
        elif name == 'tap':
            interval = self.DEFAULT_TAP_INTERVAL if action.interval is None else action.interval
            self._tap(current_char, int(action.value), interval)
        elif name == 'attack':
            interval = self.DEFAULT_TAP_INTERVAL if action.interval is None else action.interval
            current_char.continues_normal_attack(float(action.value), interval=interval)
        elif name == 'heavy':
            current_char.heavy_attack(float(action.value or self.DEFAULT_HEAVY_DURATION))
        elif name == 'sleep':
            current_char.sleep(float(action.value))
        elif name == 'resonance':
            current_char.click_resonance()
        elif name == 'liberation':
            self._click_liberation(current_char)
        elif name == 'echo':
            current_char.click_echo()
        elif name == 'dodge':
            self._send_config_key('Dodge Key', action.value)
        elif name == 'jump':
            self.task.jump(after_sleep=self._optional_float(action.value, self.DEFAULT_KEY_AFTER_SLEEP))
        else:
            raise CustomRotationConfigError(f'第{action.line_no}行未知动作: {action.raw}')

    def _tap(self, current_char, count, interval):
        for _ in range(count):
            current_char.normal_attack()
            current_char.sleep(interval)

    def _click_liberation(self, current_char):
        old_use_liberation = self.task.use_liberation
        self.task.use_liberation = True
        try:
            current_char.click_liberation()
        finally:
            self.task.use_liberation = old_use_liberation

    def _send_config_key(self, key_name, after_sleep):
        key = self.task.key_config.get(key_name)
        if not key:
            raise CustomRotationConfigError(f'未配置按键: {key_name}')
        self.task.send_key(key, after_sleep=self._optional_float(after_sleep, self.DEFAULT_KEY_AFTER_SLEEP))

    def _switch_to(self, position):
        target_index = position - 1
        in_team, current_index, count = self.task.in_team()
        if not in_team:
            self.task.raise_not_in_combat('custom rotation switch failed: not in team')
        if position < 1 or position > count:
            raise CustomRotationConfigError(f'切换目标不存在: switch:{position}')
        current_char = self.task.get_current_char(raise_exception=True)
        if current_char.index == target_index:
            return
        switch_to = self.task.chars[target_index]
        if switch_to is None:
            raise CustomRotationConfigError(f'切换目标未识别: switch:{position}')

        has_intro = current_char.get_current_con() == 1
        start = time.time()
        last_click = 0
        while True:
            self.task.check_combat()
            now = time.time()
            in_team, current_index, _ = self.task.in_team()
            if in_team and current_index == target_index:
                current_char.switch_out()
                for char in self.task.chars:
                    if char:
                        char.is_current_char = (char.index == current_index)
                switch_to.has_intro = has_intro
                if has_intro:
                    current_time = time.time()
                    self.task.add_freeze_duration(current_time, switch_to.intro_motion_freeze_duration, -100)
                    current_char.last_outro_time = current_time
                return
            if now - start > getattr(self.task, 'switch_char_time_out', 5):
                self.task.raise_not_in_combat(f'custom rotation switch:{position} timeout')
            if now - last_click > 0.1:
                self.task.send_key(str(position))
                self.task.sleep(0.001)
                self.task.click()
                self.task.sleep(0.001)
                last_click = now
            self.task.next_frame()

    def _parse(self, script):
        actions = []
        for line_no, raw_line in enumerate(script.splitlines(), 1):
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue
            actions.append(self._parse_line(line_no, line))
        return actions

    def _parse_line(self, line_no, line):
        command, interval = self._split_interval(line_no, line)
        name, value = self._split_value(command)
        name = self._normalize_name(name)
        self._validate(line_no, line, name, value, interval)
        return RotationAction(line_no=line_no, raw=line, name=name, value=value, interval=interval)

    def _split_interval(self, line_no, line):
        parts = line.split('@', 1)
        if len(parts) == 1:
            return parts[0].strip(), None
        try:
            return parts[0].strip(), float(parts[1].strip())
        except ValueError as exc:
            raise CustomRotationConfigError(f'第{line_no}行间隔不是数字: {line}') from exc

    def _split_value(self, command):
        parts = command.split(':', 1)
        if len(parts) == 1:
            return parts[0].strip().lower(), None
        return parts[0].strip().lower(), parts[1].strip()

    def _normalize_name(self, name):
        aliases = {
            'click': 'tap',
            'na': 'tap',
            'normal': 'tap',
            'normal_attack': 'tap',
            'res': 'resonance',
            'skill': 'resonance',
            'e': 'resonance',
            'lib': 'liberation',
            'ult': 'liberation',
            'r': 'liberation',
            'q': 'echo',
            'swap': 'switch',
            'wait': 'sleep',
            'dash': 'dodge',
            '切人': 'switch',
            '普攻': 'tap',
            '点击': 'tap',
            '连续普攻': 'attack',
            '重击': 'heavy',
            '等待': 'sleep',
            '共鸣技能': 'resonance',
            '技能': 'resonance',
            '共鸣解放': 'liberation',
            '大招': 'liberation',
            '声骸': 'echo',
            '闪避': 'dodge',
            '跳跃': 'jump',
        }
        return aliases.get(name, name)

    def _validate(self, line_no, raw, name, value, interval):
        if name not in {
            'switch', 'tap', 'attack', 'heavy', 'sleep',
            'resonance', 'liberation', 'echo', 'dodge', 'jump',
        }:
            raise CustomRotationConfigError(f'第{line_no}行未知动作: {raw}')
        if interval is not None and interval < 0:
            raise CustomRotationConfigError(f'第{line_no}行动作间隔不能小于0: {raw}')
        if interval is not None and name not in {'tap', 'attack'}:
            raise CustomRotationConfigError(f'第{line_no}行只有 tap/attack 支持 @间隔: {raw}')
        if name == 'switch':
            if value is not None and not self._is_int_in_range(value, 1, 3):
                raise CustomRotationConfigError(f'第{line_no}行 switch 只能是 1/2/3: {raw}')
        elif name == 'tap':
            if not self._is_positive_int(value):
                raise CustomRotationConfigError(f'第{line_no}行 tap 需要正整数次数: {raw}')
        elif name in {'attack', 'sleep'}:
            if not self._is_non_negative_float(value):
                raise CustomRotationConfigError(f'第{line_no}行 {name} 需要秒数: {raw}')
        elif name == 'heavy':
            if value is not None and not self._is_non_negative_float(value):
                raise CustomRotationConfigError(f'第{line_no}行 heavy 需要秒数: {raw}')
        elif name in {'dodge', 'jump'}:
            if value is not None and not self._is_non_negative_float(value):
                raise CustomRotationConfigError(f'第{line_no}行 {name} 需要秒数: {raw}')
        elif value is not None:
            raise CustomRotationConfigError(f'第{line_no}行 {name} 不支持参数: {raw}')

    def _optional_float(self, value, default):
        if value is None:
            return default
        return float(value)

    def _is_positive_int(self, value):
        return self._is_int_in_range(value, 1, 999)

    def _is_int_in_range(self, value, minimum, maximum):
        if value is None:
            return False
        try:
            parsed = int(value)
        except ValueError:
            return False
        return minimum <= parsed <= maximum

    def _is_non_negative_float(self, value):
        if value is None:
            return False
        try:
            parsed = float(value)
        except ValueError:
            return False
        return parsed >= 0
