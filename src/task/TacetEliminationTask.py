"""Temporary Tacet Elimination event, using pixels and OCR without new assets."""
import re

import cv2
import numpy as np

from src.task.BaseWWTask import BaseWWTask
from src.task.MouseResetTask import MouseResetTask
from src.task.WWOneTimeTask import WWOneTimeTask


ROWS, COLS = 7, 8


def cell_position(row, col):
    return 0.484 + col * 0.0645, 0.182 + row * 0.1135


def read_board(frame):
    """Classify the five echo colours, bottles and rainbow pieces from HSV."""
    height, width = frame.shape[:2]
    board = []
    for row in range(ROWS):
        line = []
        for col in range(COLS):
            x, y = cell_position(row, col)
            crop = frame[int((y - .043) * height):int((y + .043) * height),
                         int((x - .024) * width):int((x + .024) * width)]
            hue, saturation, value = cv2.split(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))
            bright = (saturation > 70) & (value > 100)
            white = np.mean((saturation < 60) & (value > 160))
            counts = [np.mean(bright & mask) for mask in (
                (hue < 12) | (hue > 170), (hue >= 60) & (hue < 90),
                (hue >= 90) & (hue < 115), (hue >= 120) & (hue < 160))]
            if np.mean(bright & (hue >= 85) & (hue < 95)) > .25:
                kind = 'I'  # solid ice blocks break beside matches, never swap
            elif np.mean(bright & (hue >= 15) & (hue < 35)) > .20 and counts[3] < .10:
                kind = 'H'  # hourglass: deliver to the bottom to gain turns
            elif white > .30:
                kind = 'W'
            elif counts[3] > .12 and white > .14 and np.mean(bright & (hue >= 12) & (hue < 35)) < .12:
                kind = 'O'  # energy bottle, damaged by adjacent eliminations
            elif np.mean(bright & (hue >= 150) & (hue < 175)) > .10:
                kind = '*'
            elif max(counts) > .08:
                kind = 'RGBP'[int(np.argmax(counts))]
            else:
                kind = '?'
            line.append(kind)
        board.append(line)
    return board


def matches(board):
    groups = []
    for vertical in (False, True):
        for outer in range(COLS if vertical else ROWS):
            cells = [(inner, outer) if vertical else (outer, inner)
                     for inner in range(ROWS if vertical else COLS)]
            start = 0
            while start < len(cells):
                end = start + 1
                kind = board[cells[start][0]][cells[start][1]]
                while end < len(cells) and board[cells[end][0]][cells[end][1]] == kind:
                    end += 1
                if end - start >= 3 and kind in 'RGBPW':
                    groups.append(set(cells[start:end]))
                start = end
    return groups


def choose_move(board, excluded=()):
    """Score legal swaps, favouring bottle damage and special-piece creation."""
    candidates = []
    for row in range(ROWS):
        for col in range(COLS):
            for dr, dc in ((0, 1), (1, 0)):
                other = row + dr, col + dc
                if other[0] >= ROWS or other[1] >= COLS:
                    continue
                a, b = (row, col), other
                if (a, b) in excluded:
                    continue
                first, second = board[row][col], board[other[0]][other[1]]
                if first in 'OI?' or second in 'OI?' or (first == second and first != '*'):
                    continue
                swapped = [line[:] for line in board]
                swapped[row][col], swapped[other[0]][other[1]] = second, first
                groups = matches(swapped)
                cleared = set().union(*groups) if groups else set()
                if '*' in (first, second):
                    colour = second if first == '*' else first
                    cleared |= {(r, c) for r in range(ROWS) for c in range(COLS)
                                if colour == '*' or swapped[r][c] == colour}
                elif not any(a in group or b in group for group in groups):
                    continue
                bottles = sum(any(abs(r - rr) <= 1 and abs(c - cc) <= 1 for rr, cc in cleared)
                              for r in range(ROWS) for c in range(COLS) if swapped[r][c] == 'O')
                ice = sum(any(abs(r - rr) + abs(c - cc) == 1 for rr, cc in cleared)
                          for r in range(ROWS) for c in range(COLS) if swapped[r][c] == 'I')
                score = len(cleared) + bottles * 7 + ice * 3 + sum(max(0, len(g) - 3) * 5 for g in groups)
                for r in range(ROWS):
                    for c in range(COLS):
                        if swapped[r][c] == 'H':
                            score += sum(rr > r and cc == c for rr, cc in cleared) * 7
                if first == 'H':
                    score += (other[0] - row) * 7
                elif second == 'H':
                    score += (row - other[0]) * 7
                candidates.append((score, a, b))
    return max(candidates, default=None)


class TacetEliminationTask(WWOneTimeTask, BaseWWTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Tacet Elimination'
        self.description = 'Start on the current event screen. Complete prerequisite stages, then play Final Elimination for the highest possible score until turns run out.'

    def event_text(self):
        return self.ocr(0, 0, 1, .96)

    @staticmethod
    def text(boxes):
        return ' '.join(box.name for box in boxes)

    def is_board(self):
        return bool(self.ocr(0, .15, .4, .23, match=re.compile('回合|[Tt]urn|[Mm]ove')))

    def play_board(self):
        failed = set()
        previous = None
        stagnant = 0
        step = 0
        # Hourglasses can extend the final stage beyond any fixed move limit.
        # Capture/sleep calls remain cancellation points; stalls still fail below.
        while True:
            self.next_frame()
            if self.dismiss_event_help():
                self.wait_board_settled()
                continue
            if not self.is_board():
                return
            board = read_board(self.frame)
            signature = tuple(map(tuple, board))
            if signature != previous:
                failed.clear()
                stagnant = 0
            else:
                stagnant += 1
            if stagnant > 8:
                self.screenshot('tacet_unrecognized_board')
                raise RuntimeError('棋盘未变化或无法识别，请检查活动界面')
            if sum(line.count('?') for line in board) > 4:
                # The board slides in after its turn counter becomes visible.
                previous = signature
                self.sleep(.5)
                continue
            move = choose_move(board, failed)
            if move is None:
                raise RuntimeError(f'No legal move recognized: {board}')
            score, start, end = move
            step += 1
            self.info_set('Move', step)
            self.log_info(f'Elimination move {start} -> {end}, score={score}; board={signature}')
            self.swap(start, end)
            self.sleep(.8)
            failed.add((start, end))
            previous = signature
            self.wait_board_settled()

    def swap(self, start, end):
        self.drag_relative(cell_position(*start), cell_position(*end))

    def drag_relative(self, first, last, smooth=False):
        from ok.device.interaction_methods.pynput import PynputInteraction

        # The event's drag control reads the real cursor during a drag.
        # Normal event buttons continue to use the configured interaction.
        interaction = self.executor.interaction
        if hasattr(interaction, 'hwnd_window'):
            interaction.hwnd_window.bring_to_front()
            if not self.wait_until(interaction.hwnd_window.is_foreground, time_out=2):
                raise RuntimeError('无法聚焦游戏窗口，已停止棋盘拖动')
            drag = PynputInteraction(interaction.capture, interaction.hwnd_window)
            if not smooth:
                drag.swipe(int(first[0] * self.width), int(first[1] * self.height),
                           int(last[0] * self.width), int(last[1] * self.height), 600)
                self.reset_scene()
                return
            x, y = first[0] * self.width, first[1] * self.height
            drag.mouse_down(int(x), int(y))
            try:
                for step in range(1, 31):
                    if not interaction.hwnd_window.is_foreground():
                        raise RuntimeError('游戏窗口失去焦点，已停止拖动')
                    drag.move(int(x + (last[0] * self.width - x) * step / 30),
                              int(y + (last[1] * self.height - y) * step / 30))
                    self.sleep(.02)
            finally:
                # Always release our own real mouse press, even on cancellation
                # or focus loss. Only this release bypasses the focus guard.
                drag.check_clickable = False
                drag.mouse_up()
            self.reset_scene()
        else:
            self.swipe_relative(*first, *last, duration=.6)

    def wait_board_settled(self):
        previous = None
        stable = 0
        for _ in range(24):
            self.sleep(.2)
            self.next_frame()
            current = tuple(map(tuple, read_board(self.frame)))
            stable = stable + 1 if current == previous else 0
            if stable >= 3:
                return
            previous = current

    def run(self):
        self.prepare_event()
        WWOneTimeTask.run(self)
        mouse_reset = self.get_task_by_class(MouseResetTask)
        was_enabled = mouse_reset.enabled
        # Its asynchronous mouse_up interrupts both list drags and board swaps.
        # Suspend only runtime state, preserving the user's persisted setting.
        mouse_reset._enabled = False
        try:
            self.sleep(.1)
            self.run_event()
        finally:
            # Respect a user change made while this long-running task was active.
            restore_enabled = mouse_reset.config.get('_enabled', was_enabled)
            mouse_reset._enabled = restore_enabled
            if restore_enabled:
                mouse_reset.post_mouse_reset(.01)

    def run_event(self):
        self.completed_stages = 0
        self.claimed_rewards = 0
        self.final_stage = self.is_board() and bool(self.ocr(
            0, .20, .4, .27, match=re.compile(r'暂无记录|最高|纪录|记录|Best|Record', re.I)))
        final_finished = False
        played_board = False
        self.info_set('Retries', 0)
        after_result = False
        unknown_frames = 0
        # Detail pages must also pass the prerequisite sweep before starting.
        if not self.is_board() and self.ocr(.6, .8, 1, .96, match=re.compile(
                r'开始挑战|Start Challenge', re.I)):
            self.return_to_stage_list()
        for _ in range(100):
            self.next_frame()
            if self.is_board():
                unknown_frames = 0
                played_board = True
                self.play_board()
                self.sleep(1)
                continue
            boxes = self.event_text()
            text = self.text(boxes)
            self.log_info(f'Event screen: {text}')
            if re.search(r'挑战成功|Challenge (?:Complete|Success)', text, re.I):
                self.screenshot('tacet_stage_success')
                if not self.wait_until(lambda: self.click_text(
                        self.event_text(), r'退出关卡|Exit|Leave'), time_out=8):
                    raise RuntimeError('未找到结算退出按钮')
                self.completed_stages += 1
                self.info_set('Completed stages', self.completed_stages)
                final_finished |= self.final_stage
                after_result = True
                continue
            if self.click_text(boxes, r'再试一次|再次挑战|重新挑战|重新开始|Retry|Try Again'):
                self.info_set('Retries', self.info.get('Retries', 0) + 1)
                if self.info.get('Retries', 0) > 3:
                    raise RuntimeError('关卡重试超过上限')
                continue
            if after_result and re.search(r'开始挑战|Start Challenge', text, re.I):
                # Resuming in the middle of a board may miss its record label.
                # Its resulting detail page still identifies the finished stage.
                if played_board and re.search(r'终局消除|Final Elimination', text, re.I):
                    self.final_stage = True
                    final_finished = True
                self.return_to_stage_list()
                after_result = False
                if final_finished:
                    self.screenshot('tacet_final_score_completed')
                    self.log_info('终局消除本局已自然结算，可再次启动任务继续冲分', notify=True)
                    return
                continue
            if self.click_text(boxes, r'开始挑战|Start Challenge'):
                if not self.wait_until(self.is_board, time_out=3):
                    # The foreground event sometimes ignores a posted button
                    # click after a real drag. Retry only the still-visible Start.
                    start = self.ocr(.6, .8, 1, .96, match=re.compile(r'开始挑战|Start Challenge', re.I))
                    if not start:
                        raise RuntimeError('开始挑战后未检测到棋盘或开始按钮')
                    self.foreground_click(start[0])
                    if not self.wait_until(self.is_board, time_out=10):
                        raise RuntimeError('开始挑战后未检测到棋盘')
                self.wait_board_settled()
                continue
            if self.click_text(boxes, r'^领取$|一键领取|全部领取|^Claim(?: All)?$'):
                self.claimed_rewards += 1
                self.info_set('Claimed rewards', self.claimed_rewards)
                continue
            if re.search(r'获得奖励|Rewards Obtained|获得物品', text, re.I):
                self.click(.5, .91, after_sleep=.5)
                continue
            if re.search(r'已完成|进行中|未开始|未完成|暂无记录|最高[纪记]录|解锁|Completed|In Progress|No Record|Best|[Uu]nlock', text, re.I):
                after_result = False
                if final_finished:
                    self.screenshot('tacet_final_score_completed')
                    self.log_info('终局消除本局已自然结算，可再次启动任务继续冲分', notify=True)
                    return
                if self.open_unfinished_stage():
                    continue
                raise RuntimeError('未找到已解锁的终局消除关卡')
            # Cascades and victory banners briefly obscure OCR text.
            unknown_frames += 1
            if unknown_frames < 12:
                self.sleep(.5)
                continue
            self.screenshot('tacet_unknown_screen')
            raise RuntimeError(f'无法识别无音消除界面: {text}')
        raise RuntimeError('超过活动页面操作上限')

    def click_text(self, boxes, pattern):
        for box in boxes:
            if re.search(pattern, box.name, re.I):
                self.click(box, after_sleep=.7)
                return True
        return False

    def foreground_click(self, box):
        from ok.device.interaction_methods.pynput import PynputInteraction

        interaction = self.executor.interaction
        window = interaction.hwnd_window
        window.bring_to_front()
        if not self.wait_until(window.is_foreground, time_out=2):
            raise RuntimeError('无法聚焦游戏窗口，已停止点击')
        click = PynputInteraction(interaction.capture, window)
        click.click(int(box.x + box.width / 2), int(box.y + box.height / 2), down_time=.1)
        self.reset_scene()

    def return_to_stage_list(self):
        self.send_key('esc', after_sleep=.7)
        on_details = lambda: bool(self.ocr(.6, .8, 1, .96, match=re.compile(
            r'开始挑战|Start Challenge', re.I)))
        if self.wait_until(lambda: not on_details(), time_out=2):
            return
        from ok.device.interaction_methods.pynput import PynputInteraction

        interaction = self.executor.interaction
        window = interaction.hwnd_window
        window.bring_to_front()
        if not self.wait_until(window.is_foreground, time_out=2):
            raise RuntimeError('无法聚焦游戏窗口，不能返回选关列表')
        PynputInteraction(interaction.capture, window).send_key('esc', down_time=.1)
        self.reset_scene()
        if not self.wait_until(lambda: not on_details(), time_out=5):
            raise RuntimeError('返回选关列表失败')

    def prepare_event(self):
        """Keep the current event page; close only its documented help overlays."""
        self.next_frame()
        self.dismiss_event_help()
        if self.ocr(.2, .1, .5, .2, match=re.compile('效果说明|Effect Details', re.I)):
            self.click(.812, .157, after_sleep=.5)
        if not self.ocr(0, 0, .4, .13, match=re.compile('无音消除|Tacet', re.I)) and not self.ocr(
                .3, .4, .7, .6, match=re.compile('挑战成功|挑战失败|Challenge', re.I)):
            raise RuntimeError('请在无音消除活动界面启动任务')

    def dismiss_event_help(self):
        if not self.ocr(0, .25, .4, .4, match=re.compile('棋子说明|基础操作|Basic Rules|Hourglass', re.I)):
            return False
        if not self.click_text(self.ocr(.3, .84, .7, .96), r'确认|Confirm|OK'):
            self.click(.964, .225, after_sleep=.5)
        return True

    def open_unfinished_stage(self):
        # Start the sweep at the left edge even after resuming midway through
        # the event. OCR status labels belong to the card immediately above.
        for _ in range(5):
            self.drag_relative((.25, .8), (.85, .8), smooth=True)
            self.sleep(.3)
        previous = None
        previous_final_x = None
        completed_seen = False
        earlier_stages_seen = False
        for _ in range(16):
            self.next_frame()
            boxes = self.ocr(0, .18, 1, .96)
            text = self.text(boxes)
            self.log_info(f'Stage sweep: {text}')
            final_boxes = [box for box in boxes if re.search(
                r'终局消除|Final Elimination', box.name, re.I)]
            completed = [box for box in boxes if re.search(
                r'^(?:已|包)?完成$|^Completed$', box.name, re.I)]
            completed_seen |= bool(completed)
            earlier_stages_seen |= len(completed) >= 2 and not final_boxes
            for box in boxes:
                # A record (including "No Record") belongs to the repeatable
                # final stage. Only prerequisite progress drives this branch.
                if re.search(r'进行中|未开始|未完成|In Progress|Not Started|[01]\s*/\s*2', box.name, re.I):
                    self.final_stage = False
                    self.click((box.x + box.width / 2) / self.width,
                               (box.y + box.height / 2) / self.height - .20, after_sleep=.7)
                    return True
            if re.search(r'未解锁|后解锁|尚未开放|Locked|Unlocks? in', text, re.I):
                raise RuntimeError('仍有关卡未解锁，无法确认全部前置关卡已完成')
            final_x = final_boxes[0].x if final_boxes else None
            final_at_end = (final_x is not None and previous_final_x is not None
                            and abs(final_x - previous_final_x) < self.width * .015)
            if final_at_end or text == previous:
                if not completed_seen or not earlier_stages_seen:
                    raise RuntimeError('无法确认关卡完成状态')
                if final_boxes:
                    self.final_stage = True
                    self.log_info('前置关卡扫描完成，进入终局消除冲分（已有纪录也会挑战）')
                    self.click(final_boxes[0], after_sleep=.7)
                    return True
                raise RuntimeError('选关列表未到达终局消除，请检查拖动或识别')
            previous = text
            previous_final_x = final_x
            self.drag_relative((.7, .8), (.35, .8), smooth=True)
            self.sleep(.8)
        raise RuntimeError('未能确认选关列表末尾')
