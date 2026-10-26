"""Temporary Tacet Elimination event, using pixels and OCR without new assets."""
import re

import cv2
import numpy as np

from src.task.BaseWWTask import BaseWWTask
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
        self.description = 'Start on the Tacet Elimination event screen. Complete unfinished stages and claim rewards.'

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
        for step in range(120):
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
            self.info_set('Move', step + 1)
            self.log_info(f'Elimination move {start} -> {end}, score={score}; board={signature}')
            self.swap(start, end)
            self.sleep(.8)
            failed.add((start, end))
            previous = signature
            self.wait_board_settled()
        raise RuntimeError('超过单关操作上限')

    def swap(self, start, end):
        self.drag_relative(cell_position(*start), cell_position(*end))

    def drag_relative(self, first, last):
        from ok.device.interaction_methods.pynput import PynputInteraction

        # The event's drag control reads the real cursor during a drag.
        # Normal event buttons continue to use the configured interaction.
        interaction = self.executor.interaction
        if hasattr(interaction, 'hwnd_window'):
            interaction.hwnd_window.bring_to_front()
            drag = PynputInteraction(interaction.capture, interaction.hwnd_window)
            drag.swipe(int(first[0] * self.width), int(first[1] * self.height),
                       int(last[0] * self.width), int(last[1] * self.height), 600)
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
        self.completed_stages = 0
        self.claimed_rewards = 0
        self.info_set('Retries', 0)
        after_result = False
        unknown_frames = 0
        for _ in range(100):
            self.next_frame()
            if self.is_board():
                unknown_frames = 0
                self.play_board()
                self.sleep(1)
                continue
            boxes = self.event_text()
            text = self.text(boxes)
            self.log_info(f'Event screen: {text}')
            if self.click_text(boxes, r'再试一次|再次挑战|重新挑战|重新开始|Retry|Try Again'):
                self.info_set('Retries', self.info.get('Retries', 0) + 1)
                if self.info.get('Retries', 0) > 3:
                    raise RuntimeError('关卡重试超过上限')
                continue
            if re.search(r'挑战成功|Challenge (?:Complete|Success)', text, re.I):
                self.screenshot('tacet_stage_success')
                if not self.click_text(boxes, r'退出关卡|Exit|Leave'):
                    raise RuntimeError('未找到结算退出按钮')
                self.completed_stages += 1
                self.claimed_rewards += 1
                self.info_set('Completed stages', self.completed_stages)
                self.info_set('Claimed rewards', self.claimed_rewards)
                after_result = True
                continue
            if after_result and re.search(r'开始挑战|Start Challenge', text, re.I):
                self.send_key('esc', after_sleep=.7)
                after_result = False
                continue
            if self.click_text(boxes, r'开始挑战|Start Challenge'):
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
            if re.search(r'已完成|进行中|未开始|未完成|解锁|Completed|In Progress|[Uu]nlock', text, re.I):
                after_result = False
                if self.open_unfinished_stage():
                    continue
                self.screenshot('tacet_all_stages_completed')
                self.log_info('无音消除当前已开放关卡已完成，奖励已领取', notify=True)
                return
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
            self.drag_relative((.25, .55), (.85, .55))
            self.sleep(.3)
        previous = None
        completed_seen = False
        for _ in range(16):
            self.next_frame()
            boxes = self.ocr(0, .18, 1, .96)
            text = self.text(boxes)
            self.log_info(f'Stage sweep: {text}')
            completed_seen |= bool(re.search(r'完成|Completed', text, re.I))
            for box in boxes:
                if re.search(r'进行中|未开始|未完成|In Progress|Not Started|[01]\s*/\s*2', box.name, re.I):
                    self.click((box.x + box.width / 2) / self.width,
                               (box.y + box.height / 2) / self.height - .20, after_sleep=.7)
                    return True
            if text == previous:
                if not completed_seen:
                    raise RuntimeError('无法确认关卡完成状态')
                return False
            previous = text
            self.drag_relative((.7, .55), (.35, .55))
            self.sleep(.8)
        raise RuntimeError('未能确认选关列表末尾')
