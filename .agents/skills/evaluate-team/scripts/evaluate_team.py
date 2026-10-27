"""Submit this file through ok-script MCP run_task; configure a copy for overrides."""

import json
import inspect
import re
import statistics
import time
import unicodedata
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import cv2
from ok import BaseTask
from src.task.AutoCombatTask import AutoCombatTask
from src.task.BaseCombatTask import NotInCombatException

RUNS = 3
METRIC = 'score'  # 'score' or 'remaining_time'
SAMPLE_INTERVAL = 0.5
COMBAT_TIMEOUT = 360
RESULT_TIMEOUT = 20
MAX_TIMER_AGE = 2.0
NO_INPUT_TIMEOUT = 8.0


class CombatStallError(TimeoutError):
    pass


def validate_team_roles(team, settings):
    for char in team:
        if char['name'] == 'Roccia' and settings.get('Roccia C6') and char['role'] != 'MainDps':
            raise AssertionError(f'Roccia C6 is enabled but the loaded class reports {char["role"]}; inspect its source/overrides')


def character_source(char):
    try:
        return inspect.getfile(type(char))
    except TypeError:
        # Team modules loaded from a file are not registered in sys.modules.
        return type(char).do_perform.__code__.co_filename

SUCCESS = re.compile(r'挑战成功|挑戰成功|挑战完成|挑戰完成|Challenge\s*(?:Complete|Success)|Victory', re.I)
FAILURE = re.compile(r'挑战失败|挑戰失敗|Challenge\s*Failed|Defeat', re.I)
RESULT = re.compile(r'挑战结束|挑戰結束|挑战结算|挑戰結算|重新挑战|重新挑戰|再次挑战|再次挑戰|Rechallenge', re.I)
SCORE_LABEL = re.compile(r'(?:(?:最终|最終|本次|挑战|挑戰|总|總)\s*)?(?:得分|积分|積分|分数|分數)|(?:final|total|challenge|team)\s*score|^score$', re.I)


def parse_remaining_time(text):
    text = unicodedata.normalize('NFKC', text).strip()
    match = re.fullmatch(r'(\d{1,2})\s*:\s*([0-5]\d)(?:\s*[:.]\s*(\d{1,2}))?', text)
    return int(match[1]) * 60 + int(match[2]) + (int(match[3]) / 10 ** len(match[3]) if match[3] else 0) if match else None


def parse_score(text):
    text = unicodedata.normalize('NFKC', text).strip()
    match = re.fullmatch(r'[△▲]?\s*(\d{1,3}(?:[,，]\d{3})+|\d+)(?:\s*分)?', text)
    return int(match[1].replace(',', '').replace('，', '')) if match else None


def read_remaining_time(task):
    box = task.box_of_screen_scaled(3840, 2160, 1820, 266, 2100, 340,
                                    name='evaluation_countdown', hcenter=True)
    readings = [(item, parse_remaining_time(item.name)) for item in task.ocr(box=box)]
    readings = [(item, value) for item, value in readings if value is not None]
    return max(readings, key=lambda pair: pair[0].confidence)[1] if readings else None


def read_final_score(boxes):
    """Only associate a numeric value with a score label, never arbitrary HUD digits."""
    candidates = []
    team_label_seen = False
    for label in boxes:
        if not SCORE_LABEL.search(label.name) or re.search(r'最高|历史|歷史|best|record', label.name, re.I):
            continue
        # This benchmarks the current team; totals may include earlier teams.
        priority = 2 if re.search(r'队伍|隊伍|team', label.name, re.I) else 1
        team_label_seen = team_label_seen or priority == 2
        inline = re.search(r'(?:得分|积分|積分|分数|分數|score)\s*[:：]?\s*([\d,，]+)\s*$', label.name, re.I)
        if inline and (value := parse_score(inline[1])) is not None:
            candidates.append((priority, value))
            continue
        for number in boxes:
            value = parse_score(number.name)
            if value is None or number is label:
                continue
            # Nearby value to the right or directly under the result's score label.
            height = max(label.height, number.height)
            same_line = abs(number.y - label.y) <= height and 0 <= number.x - (label.x + label.width) <= height * 10
            underneath = 0 < number.y - label.y <= height * 4 and abs((number.x + number.width / 2) - (label.x + label.width / 2)) <= height * 6
            if same_line or underneath:
                candidates.append((priority, value))
    best_priority = 2 if team_label_seen else max((priority for priority, _ in candidates), default=0)
    values = {value for priority, value in candidates if priority == best_priority}
    return values.pop() if len(values) == 1 else None


def summarize(values):
    if not values:
        return {'count': 0}
    return dict(count=len(values), mean=statistics.mean(values), median=statistics.median(values),
                best=max(values), worst=min(values), range=max(values) - min(values),
                sample_stdev=statistics.stdev(values) if len(values) > 1 else None)


def valid_result(metric, outcome, value, timer_age, combat_error=None, disappearance_gap=None):
    if value is None or outcome in ('failure', 'unrecognized'):
        return False
    if combat_error and combat_error.startswith(('CharDeadException', 'CharRevivedException', 'TimeoutError', 'CombatStallError')):
        return False
    if metric == 'remaining_time':
        freshness = disappearance_gap if disappearance_gap is not None else timer_age
        return outcome == 'success' and freshness is not None and 0 <= freshness <= MAX_TIMER_AGE
    return outcome in ('success', 'ended')


class Recorder:
    def __init__(self, task, directory):
        self.task = task
        self.directory = directory
        self.start = time.monotonic()
        self.next_sample = 0
        self.sampling = False
        self.last_timer = None
        self.last_timer_at = None
        self.last_timer_frame = None
        self.timer_disappeared_at = None
        self.success_at = None
        self.success_frame = None
        self.failure_seen = False
        self.samples = []
        self.actions = Counter()
        self.rotations = []
        self.switches = []
        self.sampling_seconds = 0
        self.timer_anomalies = 0
        self.last_input_at = self.start
        self.rotation_char = None
        self.rotation_at = self.start
        self.next_heartbeat = 0
        self.stalls = []
        self.events = (directory / 'events.jsonl').open('w', encoding='utf-8')

    def emit(self, event, **values):
        self.events.write(json.dumps(dict(event=event, elapsed=round(time.monotonic() - self.start, 3), **values)) + '\n')
        self.events.flush()

    def sample(self):
        now = time.monotonic()
        if now - self.start > COMBAT_TIMEOUT:
            raise TimeoutError('Abyss combat exceeded evaluation timeout')
        if self.sampling or now < self.next_sample or self.success_at is not None or self.failure_seen:
            return
        self.next_sample = now + SAMPLE_INTERVAL
        self.sampling = True
        try:
            if now >= self.next_heartbeat:
                self.next_heartbeat = now + 2
                (self.directory / 'heartbeat.json').write_text(json.dumps(dict(
                    captured_at=time.time(), char=self.rotation_char,
                    rotation_seconds=round(now-self.rotation_at, 3),
                    last_input_age=round(now-self.last_input_at, 3), timer=self.last_timer)), encoding='utf-8')
            if (self.last_timer_at is not None and now-self.last_timer_at < 2
                    and now-self.last_input_at > NO_INPUT_TIMEOUT
                    and not self.task.in_liberation):
                self.stalls.append(dict(char=self.rotation_char, seconds=now-self.last_input_at))
                cv2.imwrite(str(self.directory / 'stall.png'), self.task.frame)
                self.emit('stall', **self.stalls[-1])
                raise CombatStallError(f'{self.rotation_char} sent no input for {now-self.last_input_at:.1f}s with the countdown active')
            value = read_remaining_time(self.task)
            if value is not None:
                # Reject obvious OCR jumps; missing readings never erase the last frame.
                if self.last_timer is not None and (value > self.last_timer or self.last_timer - value > now - self.last_timer_at + 3):
                    self.timer_anomalies += 1
                    return
                self.last_timer, self.last_timer_at = value, now
                self.timer_disappeared_at = None
                self.last_timer_frame = self.task.frame.copy()
                self.samples.append(dict(elapsed=round(now - self.start, 3), seconds=value))
            elif METRIC == 'remaining_time' and self.last_timer_at is not None:
                self.timer_disappeared_at = self.timer_disappeared_at or now
                # Success can flash during a character's animation wait, before
                # the ordinary combat loop returns. Preserve that observation.
                boxes = self.task.ocr(box=self.task.box_of_screen(0.15, 0.15, 0.85, 0.75))
                text = '\n'.join(b.name for b in boxes)
                if SUCCESS.search(text):
                    self.success_at = time.monotonic()
                    self.success_frame = self.task.frame.copy()
                    self.emit('visible_success', last_timer=self.last_timer)
                self.failure_seen = bool(FAILURE.search(text))
        finally:
            self.sampling_seconds += time.monotonic() - now
            self.sampling = False

    def frame_wrapper(self, original):
        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            self.sample()
            return result
        return wrapped

    def action_wrapper(self, char, name, original):
        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            succeeded = result[0] if isinstance(result, tuple) else bool(result)
            if succeeded:
                self.actions[f'{char.name}.{name}'] += 1
                self.emit('action', char=char.name, action=name)
            return result
        return wrapped

    def perform_wrapper(self, char, original):
        def wrapped(*args, **kwargs):
            start = time.monotonic()
            self.rotation_char, self.rotation_at = char.name, start
            intro = bool(char.has_intro)
            self.emit('rotation_start', char=char.name, intro=intro, con=char.current_con)
            try:
                return original(*args, **kwargs)
            finally:
                row = dict(char=char.name, intro=intro, duration=round(time.monotonic() - start, 3))
                self.rotations.append(row)
                self.emit('rotation_end', **row)
        return wrapped

    def input_wrapper(self, original):
        def wrapped(*args, **kwargs):
            self.last_input_at = time.monotonic()
            return original(*args, **kwargs)
        return wrapped

    def switch_wrapper(self, char, original):
        def wrapped(*args, **kwargs):
            con = kwargs.get('con_full', args[0] if args else False) or char.current_con == 1
            result = original(*args, **kwargs)
            row = dict(char=char.name, full_con=bool(con))
            self.switches.append(row)
            self.emit('switch_out', **row)
            return result
        return wrapped

    def install(self, stack):
        stack.callback(self.events.close)
        stack.enter_context(patch.object(self.task, 'next_frame', self.frame_wrapper(self.task.next_frame)))
        for name in ('click', 'send_key', 'send_key_down', 'mouse_down'):
            if hasattr(self.task, name):
                stack.enter_context(patch.object(self.task, name, self.input_wrapper(getattr(self.task, name))))
        for char in self.task.chars:
            stack.enter_context(patch.object(char, 'perform', self.perform_wrapper(char, char.perform)))
            stack.enter_context(patch.object(char, 'switch_out', self.switch_wrapper(char, char.switch_out)))
            for name in ('click_liberation', 'click_resonance', 'click_echo'):
                stack.enter_context(patch.object(char, name, self.action_wrapper(char, name, getattr(char, name))))


class Task(BaseTask):
    def reset_to_start(self):
        if type(RUNS) is not int or RUNS < 1 or METRIC not in ('score', 'remaining_time'):
            raise ValueError('Use a positive RUNS count and score/remaining_time metric')
        self.combat = self.get_task_by_class(AutoCombatTask)
        self.combat.next_frame()
        # Load first, before changing the arena. Results may hide portraits.
        self.initial_team = self.team() if self.combat.load_chars() else None
        if self.initial_team:
            validate_team_roles(self.initial_team, {'Roccia C6': self.combat.char_config.get('Roccia C6')})
        self.start_combat()

    def start_combat(self):
        # Recreate per-character cooldown/buff/stance caches after an arena reset.
        self.combat.chars = [None, None, None]
        self.combat.freeze_durations = []
        self.combat.restart_combat_in_abyss()

    def verify_start_state(self):
        assert self.combat.wait_until(self.combat.check_count_down, time_out=8, raise_if_not_found=True)
        self.expected_team = self.team()
        validate_team_roles(self.expected_team, {'Roccia C6': self.combat.char_config.get('Roccia C6')})
        assert len(self.expected_team) == 3 and all(c['class'] != 'BaseChar' for c in self.expected_team)
        assert self.initial_team is None or self.identity(self.initial_team) == self.identity(self.expected_team), 'Team changed during recovery'
        return True

    def team(self):
        return [dict(slot=c.index + 1, name=c.name, module=type(c).__module__,
                     source=character_source(c),
                     **{'class': type(c).__name__}, confidence=c.confidence,
                     role=str(c.char_type), buff_time=c.buff_time) for c in self.combat.chars if c is not None]

    @staticmethod
    def identity(team):
        return [(c['slot'], c['module'], c['class']) for c in team]

    def write_summary(self, data):
        values = [r['metric_value'] for r in data['runs'] if r['valid']]
        data['summary'] = summarize(values)
        (Path(self.artifact_directory) / 'evaluation.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def run(self):
        task = self.combat
        data = dict(metric=METRIC, requested=RUNS, team=self.expected_team,
                    game_language=task.game_lang, resolution=[task.frame.shape[1], task.frame.shape[0]],
                    combat_settings={key: task.config.get(key) for key in task.default_config},
                    character_settings={key: task.char_config.get(key) for key in ('Roccia C6', 'Chisa DPS', 'Iuno C6', 'Suoming DPS')},
                    sample_interval=SAMPLE_INTERVAL, runs=[])
        previous_liberation = task.use_liberation
        # Mirror AutoCombatTask's Abyss liberation behavior.
        task.use_liberation = True
        try:
            for index in range(1, RUNS + 1):
                if index > 1:
                    self.start_combat()
                    assert task.wait_until(task.check_count_down, time_out=8, raise_if_not_found=True)
                assert self.identity(self.team()) == self.identity(self.expected_team), 'Team changed between combats'
                directory = Path(self.artifact_directory) / f'combat_{index}'
                directory.mkdir()
                data['attempted'] = index
                self.write_summary(data)
                cv2.imwrite(str(directory / 'start.png'), task.frame)
                recorder = Recorder(task, directory)
                row = dict(run=index, opener=task.get_current_char().name, valid=False, metric_value=None)
                combat_error = None
                with ExitStack() as stack:
                    recorder.install(stack)
                    try:
                        # Match normal auto-combat's opening support selection.
                        task.switch_healer()
                        while task.in_combat():
                            recorder.sample()
                            task.get_current_char().perform()
                            task.next_frame()
                    except (NotInCombatException, TimeoutError) as error:
                        combat_error = f'{type(error).__name__}: {error}'
                    finally:
                        row['wall_seconds'] = round(time.monotonic() - recorder.start, 3)
                # No timer sampling on the result screen: preserve the last in-combat frame.
                task.next_frame()
                early_timer = read_remaining_time(task)
                premature_exit = early_timer is not None and early_timer > 0 and recorder.success_at is None and not recorder.failure_seen
                if premature_exit:
                    cv2.imwrite(str(directory / 'premature_combat_exit.png'), task.frame)
                if recorder.last_timer_frame is not None:
                    cv2.imwrite(str(directory / 'last_timer.png'), recorder.last_timer_frame)
                if recorder.success_frame is not None:
                    cv2.imwrite(str(directory / 'success.png'), recorder.success_frame)
                result_boxes = []
                result_at = recorder.success_at
                success_seen = recorder.success_at is not None
                failure_seen = recorder.failure_seen
                stable_score = None
                stable_since = None
                deadline = time.monotonic() + (2 if premature_exit else RESULT_TIMEOUT)
                while time.monotonic() < deadline:
                    task.next_frame()
                    result_boxes = task.ocr()
                    texts = '\n'.join(b.name for b in result_boxes)
                    success_seen = success_seen or bool(SUCCESS.search(texts))
                    failure_seen = failure_seen or bool(FAILURE.search(texts))
                    if SUCCESS.search(texts) or FAILURE.search(texts) or RESULT.search(texts):
                        result_at = result_at or time.monotonic()
                    if result_at:
                        if failure_seen or (METRIC == 'remaining_time' and success_seen):
                            break
                        score_now = read_final_score(result_boxes)
                        if score_now is not None and score_now == stable_score:
                            if time.monotonic() - stable_since >= 0.8:
                                break
                        else:
                            stable_score, stable_since = score_now, time.monotonic()
                    task.sleep(0.25)
                texts = '\n'.join(b.name for b in result_boxes)
                cv2.imwrite(str(directory / 'result.png'), task.frame)
                (directory / 'result_ocr.json').write_text(json.dumps([dict(text=b.name, x=b.x, y=b.y, width=b.width, height=b.height, confidence=b.confidence) for b in result_boxes], indent=2, ensure_ascii=False), encoding='utf-8')
                score = read_final_score(result_boxes) if result_at else None
                outcome = 'failure' if failure_seen else 'success' if success_seen else 'ended' if result_at else 'unrecognized'
                row.update(outcome=outcome, final_score=score, remaining_seconds=recorder.last_timer,
                           timer_sample_age_seconds=round((recorder.success_at or result_at or time.monotonic()) - recorder.last_timer_at, 3) if recorder.last_timer_at else None,
                           timer_samples=recorder.samples, timer_anomalies=recorder.timer_anomalies,
                           sampling_wall_seconds=round(recorder.sampling_seconds, 3),
                           actions=dict(recorder.actions), rotations=recorder.rotations, switches=recorder.switches,
                           combat_error=combat_error, evidence=str(directory))
                row['timer_disappearance_gap_seconds'] = (round(recorder.timer_disappeared_at-recorder.last_timer_at, 3)
                                                          if recorder.timer_disappeared_at is not None and recorder.last_timer_at is not None else None)
                row['stalls'] = recorder.stalls
                row['premature_combat_exit'] = premature_exit
                row['metric_value'] = score if METRIC == 'score' else recorder.last_timer
                row['effective_opener'] = recorder.rotations[0]['char'] if recorder.rotations else None
                # Combat-end detection exceptions are expected; death/timeout are not valid results.
                bad_combat = premature_exit or bool(recorder.stalls) or (combat_error and combat_error.startswith(('CharDeadException', 'CharRevivedException', 'TimeoutError', 'CombatStallError')))
                row['valid'] = bool(result_at and valid_result(METRIC, outcome, row['metric_value'], row['timer_sample_age_seconds'], combat_error,
                                                              row['timer_disappearance_gap_seconds']))
                row['valid'] = row['valid'] and not bad_combat
                if not row['valid']:
                    row['invalid_reason'] = f'Invalid {METRIC} result: outcome={outcome}, value={row["metric_value"]}, timer_age={row["timer_sample_age_seconds"]}, combat_error={combat_error}'
                data['runs'].append(row)
                self.write_summary(data)
                print('EVALUATION_RUN', json.dumps({k: v for k, v in row.items() if k not in ('rotations', 'switches', 'timer_samples')}, ensure_ascii=False))
                task.combat_end()
                if outcome == 'unrecognized' or bad_combat:
                    break
            assert len(data['runs']) == RUNS and all(r['valid'] for r in data['runs']), 'Evaluation incomplete or contains invalid results; inspect evaluation.json'
        finally:
            task.use_liberation = previous_liberation
            task.reset_to_false(reason='team evaluation finished')
            self.write_summary(data)
