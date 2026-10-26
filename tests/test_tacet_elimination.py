import unittest
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np

from src.task.TacetEliminationTask import TacetEliminationTask, read_board, matches, choose_move


class TestTacetElimination(unittest.TestCase):
    def test_live_board_at_supported_resolutions(self):
        image = cv2.imread(str(Path(__file__).parent / 'images/tacet_elimination_board.jpg'))
        expected = ['PWBPRRPB', 'PGPPRGBP', 'GGROWBBW', 'PBBWGOWW',
                    'GRPOPBBP', 'RPGBWBGG', 'GGBPWGRB']
        for size in ((1280, 720), (1920, 1080), (3840, 2160)):
            with self.subTest(size=size):
                board = read_board(cv2.resize(image, size))
                self.assertEqual([''.join(row) for row in board], expected)
                move = choose_move(board)
                self.assertIsNotNone(move)
                _, a, b = move
                board[a[0]][a[1]], board[b[0]][b[1]] = board[b[0]][b[1]], board[a[0]][a[1]]
                self.assertTrue(any(a in group or b in group for group in matches(board)))

    def test_blank_capture_produces_no_moves(self):
        board = read_board(np.zeros((720, 1280, 3), dtype=np.uint8))
        self.assertTrue(all(cell == '?' for row in board for cell in row))
        self.assertIsNone(choose_move(board))

    def test_bottles_do_not_match_or_swap(self):
        board = [['O'] * 8 for _ in range(7)]
        self.assertEqual(matches(board), [])
        self.assertIsNone(choose_move(board))

    def test_ice_is_distinct_from_blue_echoes(self):
        image = cv2.imread(str(Path(__file__).parent / 'images/tacet_elimination_ice.jpg'))
        board = read_board(image)
        self.assertEqual(''.join(board[0]), 'IIIGWIII')
        self.assertEqual(board[1][3], 'B')
        move = choose_move(board)
        self.assertIsNotNone(move)
        for row, col in move[1:]:
            self.assertNotEqual(board[row][col], 'I')

    def test_two_rainbow_pieces_clear_whole_board(self):
        board = [['I'] * 8 for _ in range(7)]
        board[2][2] = board[2][3] = '*'
        move = choose_move(board)
        self.assertEqual(move[1:], ((2, 2), (2, 3)))
        self.assertGreaterEqual(move[0], 56)

    def test_hourglass_recognition_and_delivery_move(self):
        image = cv2.imread(str(Path(__file__).parent / 'images/tacet_elimination_hourglass.jpg'))
        board = read_board(image)
        self.assertEqual(board[2][7], 'H')
        self.assertEqual(board[3][5], 'H')
        self.assertEqual(board[5][3], 'H')
        self.assertNotIn('?', ''.join(''.join(row) for row in board))
        self.assertIsNotNone(choose_move(board))

    def test_blank_stage_list_cannot_report_completion(self):
        task = TacetEliminationTask.__new__(TacetEliminationTask)
        for name in ('next_frame', 'drag_relative', 'sleep', 'log_info', 'click'):
            setattr(task, name, Mock())
        task.ocr = Mock(return_value=[])
        with self.assertRaisesRegex(RuntimeError, '完成状态'):
            task.open_unfinished_stage()
        task.click.assert_not_called()

    def test_wrong_start_screen_does_not_click(self):
        task = TacetEliminationTask.__new__(TacetEliminationTask)
        task.next_frame = Mock()
        task.ocr = Mock(return_value=[])
        task.click = Mock()
        with self.assertRaisesRegex(RuntimeError, '活动界面'):
            task.prepare_event()
        task.click.assert_not_called()


if __name__ == '__main__':
    unittest.main()
