"""Rahai Blocks: endless mode, direct start from a stage page, and cloud input.

Covers:
1. An endless details page (no difficulty tabs) is not mistaken for an
   unrecognisable difficulty and exited;
2. A page with unreadable difficulty can still be started via the wide
   "start" button;
3. The four ways an endless round ends: goal / dead / ended / cap;
4. Cloud (browser device) needs no PC window handle and uses BrowserInteraction;
5. Normal-stage regression: a lost board is still a failure.
"""

import re
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ok import Box

from src.task.rahai_blocks import Board, Move, Piece
from src.task.RahaiBlocksTask import ChallengeFailed, RahaiBlocksTask


def box(name, x=100, y=100, width=80, height=24):
    return Box(x, y, width, height, name=name, confidence=0.99)


class FakeScreen:
    """Return OCR boxes based on the text supposedly visible on screen."""

    def __init__(self, names=()):
        self.names = list(names)

    def show(self, *names):
        self.names = list(names)

    def __call__(self, x=0, y=0, to_x=1, to_y=1, match=None, **kwargs):
        if match is None:
            return [box(name, 10 * index, 10 * index) for index, name in enumerate(self.names)]
        pattern = re.compile(re.escape(match)) if isinstance(match, str) else match
        return [box(name, 10 * index, 10 * index)
                for index, name in enumerate(self.names) if pattern.search(name)]


def make_task(names=(), board_sequence=None, score=None, goal_text=None):
    task = object.__new__(RahaiBlocksTask)
    # width / height / frame / hwnd are read-only properties backed by executor
    task._executor = SimpleNamespace(
        method=SimpleNamespace(width=1920, height=1080),
        frame=object(),
        device_manager=SimpleNamespace(hwnd_window=None, capture_method='capture'),
    )
    task.sleep = Mock()
    task.click = Mock()
    task.next_frame = Mock(return_value=object())
    task.screenshot = Mock()
    task.log_info = Mock()
    task.log_warning = Mock()
    task.info_set = Mock()
    task.is_browser = Mock(return_value=True)
    screen = FakeScreen(names if goal_text is None else (*names, goal_text))
    task.ocr = screen
    task.screen = screen

    def wait_until(func, time_out=5, settle_time=0, raise_if_not_found=False, **kwargs):
        result = func() if callable(func) else func
        if not result and raise_if_not_found:
            raise TimeoutError('not found')
        return result

    task.wait_until = Mock(side_effect=wait_until)

    boards = list(board_sequence or [])
    calls = {'n': 0}

    def playable():
        calls['n'] += 1
        if not boards:
            return None
        return boards[min(calls['n'] - 1, len(boards) - 1)]

    task._playable_board = Mock(side_effect=playable)
    task._endless_score = Mock(return_value=score)
    return task


def stable_boards(count=12):
    """Return a different board each read, to avoid the 4x-stagnation guard."""
    boards = []
    for index in range(count):
        mask = 1 << (index % 24)
        boards.append(Board(mask=mask, pieces=(Piece(0, ((0, 0),), (100, 900)),), fixed=0))
    return boards


class EndlessDetectionTest(unittest.TestCase):

    def test_endless_details_page_is_detected_without_difficulty(self):
        task = make_task(['拉海洛方块', '无尽模式'])
        self.assertTrue(task._endless_page())
        self.assertFalse(task.ocr(.68, .125, .96, .181, match=re.compile('困难$')))

    def test_normal_details_page_is_not_endless(self):
        task = make_task(['拉海洛方块', '关卡目标', '困难'])
        self.assertFalse(task._endless_page())

    def test_endless_ingame_by_score_text(self):
        task = make_task(['拉海洛方块', '达到9999分结算可得首通奖励'])
        self.assertTrue(task._endless_ingame())
        self.assertEqual(task._endless_goal(), 9999)

    def test_endless_goal_missing(self):
        task = make_task(['拉海洛方块', '无尽模式'])
        self.assertIsNone(task._endless_goal())

    def test_tutorial_confirm_clicks_confirm(self):
        task = make_task(['无尽模式', '玩家可以一直游玩，直到失败', '确认'])
        self.assertTrue(task._tutorial_confirm())
        clicked = task.click.call_args[0][0]
        self.assertEqual(clicked.name, '确认')


class DirectStartTest(unittest.TestCase):
    """Starting on a details page: the root cause of the old "exits on page" bug."""

    def test_endless_details_goes_endless_flow(self):
        task = make_task(['拉海洛方块', '无尽模式', '开始挑战'])
        task._challenge_endless = Mock()
        task._start_and_play = Mock()
        task._challenge_current_details('interaction')
        task._challenge_endless.assert_called_once_with('interaction')
        task._start_and_play.assert_not_called()

    def test_unreadable_page_starts_with_wide_button(self):
        task = make_task(['拉海洛方块', '开始挑战'])
        task._challenge_endless = Mock()
        task._start_and_play = Mock()
        task._challenge_current_details('interaction')
        task._start_and_play.assert_called_once()
        self.assertFalse(task._start_and_play.call_args.kwargs['check_objective'])
        task._challenge_endless.assert_not_called()

    def test_known_difficulty_keeps_selected_difficulty(self):
        task = make_task(['拉海洛方块', '关卡目标', '困难', '开始挑战'])
        task._start_and_play = Mock()
        task._challenge_current_details('interaction')
        self.assertIn('困难', task._start_and_play.call_args[0][1])

    def test_page_without_anything_still_fails_cleanly(self):
        task = make_task(['拉海洛方块'])
        with self.assertRaises(ChallengeFailed):
            task._challenge_current_details('interaction')


class EndlessPlayTest(unittest.TestCase):

    def test_goal_reached_quits_round(self):
        task = make_task(score=10000, goal_text='达到9999分结算可得首通奖励')
        boards = stable_boards()
        state = {'index': 0, 'board': boards[0]}

        def playable():
            state['board'] = boards[state['index'] % len(boards)]
            return state['board']

        def place(*args, **kwargs):
            state['index'] += 1
            return True

        task._playable_board = Mock(side_effect=playable)
        task._read_board = Mock(side_effect=lambda: state['board'])
        task._place = Mock(side_effect=place)
        with patch('src.task.RahaiBlocksTask.choose_move') as choose, \
                patch('src.task.RahaiBlocksTask.clear_lines',
                      side_effect=lambda mask, fixed=0: (mask, 0)):
            choose.return_value = Move(slot=0, turns=0, row=0, col=0, cells=((0, 0),), mask=0)
            reason = task._play_board('interaction', endless=True, max_moves=60)
        self.assertEqual(reason, 'goal')

    def test_no_legal_move_ends_round(self):
        task = make_task()
        task._playable_board = Mock(return_value=stable_boards()[0])
        with patch('src.task.RahaiBlocksTask.choose_move', return_value=None):
            reason = task._play_board('interaction', endless=True)
        self.assertEqual(reason, 'dead')

    def test_board_gone_ends_round(self):
        task = make_task()
        task._playable_board = Mock(return_value=None)
        task._reward = Mock(return_value=None)
        task._tutorial_confirm = Mock(return_value=False)
        task._dismiss_help = Mock(return_value=False)
        self.assertEqual(task._play_board('interaction', endless=True), 'ended')

    def test_move_cap_ends_round(self):
        task = make_task()
        board = stable_boards()[0]
        task._playable_board = Mock(return_value=board)
        task._read_board = Mock(return_value=board)
        task._place = Mock(return_value=True)
        with patch('src.task.RahaiBlocksTask.choose_move') as choose, \
                patch('src.task.RahaiBlocksTask.clear_lines', side_effect=lambda mask, fixed=0: (mask, 0)):
            choose.return_value = Move(slot=0, turns=0, row=0, col=0, cells=((0, 0),), mask=0)
            reason = task._play_board('interaction', endless=True, max_moves=1)
        self.assertEqual(reason, 'cap')

    def test_normal_round_board_lost_is_still_a_failure(self):
        task = make_task()
        task._playable_board = Mock(return_value=None)
        task._reward = Mock(return_value=None)
        task._tutorial_confirm = Mock(return_value=False)
        task._dismiss_help = Mock(return_value=False)
        with self.assertRaises(ChallengeFailed):
            task._play_board('interaction')


class CloudModeTest(unittest.TestCase):

    def test_browser_uses_browser_interaction(self):
        task = make_task()
        task.is_browser = Mock(return_value=True)
        task._executor = Mock()
        task._executor.device_manager.capture_method = 'capture'
        with patch('src.task.RahaiBlocksTask.BrowserInteraction') as browser:
            self.assertIs(task._make_interaction(), browser.return_value)
        browser.assert_called_once_with('capture')

    def test_pc_uses_pynput_interaction(self):
        task = make_task()
        task.is_browser = Mock(return_value=False)
        with patch('src.task.RahaiBlocksTask.PynputInteraction') as pynput:
            self.assertIs(task._make_interaction(), pynput.return_value)
        self.assertEqual(pynput.call_args[0][0], 'capture')

    def test_cloud_does_not_require_hwnd(self):
        """Cloud has no game window handle; the old check raised "needs Windows PC"."""
        task = make_task(['拉海洛方块'])
        task._make_interaction = Mock(return_value='interaction')
        with patch('src.task.RahaiBlocksTask.canonical_frame', return_value=object()):
            with self.assertRaises(RuntimeError) as caught:
                task.run()
        self.assertIn('请先打开', str(caught.exception))

    def test_browser_interaction_is_always_clickable(self):
        task = make_task()
        task.is_browser = Mock(return_value=True)
        interaction = Mock()
        interaction.clickable = Mock(return_value=False)
        self.assertTrue(task._clickable(interaction))

    def test_pc_requires_foreground_window(self):
        task = make_task()
        task.is_browser = Mock(return_value=False)
        interaction = Mock()
        interaction.clickable = Mock(return_value=False)
        self.assertFalse(task._clickable(interaction))


if __name__ == '__main__':
    unittest.main(verbosity=2)
