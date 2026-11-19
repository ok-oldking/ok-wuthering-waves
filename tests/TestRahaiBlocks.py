import unittest
from pathlib import Path

import cv2
import numpy as np

from src.task.rahai_blocks import (
    Board, COLS, ROWS, Piece, canonical_frame, choose_move, clear_lines, placements,
    preview_matches, read_board, score_bar_full,
)


def fixture(name):
    path = Path(__file__).with_name('images') / f'rahai_{name}.jpg'
    return canonical_frame(cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR))


class TestRahaiBlocks(unittest.TestCase):
    def test_intersecting_lines_clear_simultaneously(self):
        self.assertEqual(clear_lines(ROWS[2] | COLS[3] | 1), (1, 2))

    def test_rotations_cannot_mirror_or_wrap(self):
        moves = placements(((0, 0), (0, 1), (1, 1)))
        self.assertEqual({turns for turns, *_ in moves}, {0, 1, 2, 3})
        for _, row, col, shape, mask in moves:
            self.assertEqual(mask.bit_count(), len(shape))
            self.assertTrue(all(row + y < 8 and col + x < 8 for x, y in shape))

    def test_solver_considers_the_other_piece(self):
        square = Piece(0, ((0, 0), (0, 1), (1, 0), (1, 1)), (0, 0))
        single = Piece(1, ((0, 0),), (0, 0))
        row = ROWS[1] ^ (1 << 8)
        almost_full = row | ROWS[0] ^ 3
        board = Board(almost_full, (square, single))
        move = choose_move(board)
        self.assertEqual(move.slot, 1)
        self.assertFalse(move.mask & board.mask)
        self.assertEqual(clear_lines(board.mask | move.mask)[1], 1)

    def test_reads_real_board_and_ignores_rotation_tooltip(self):
        board = read_board(fixture('score'))
        self.assertEqual(board.mask, 27026459673497112)
        self.assertEqual([len(p.cells) for p in board.pieces], [4, 5])
        move = choose_move(board)
        self.assertEqual((move.slot, move.row, move.col), (0, 2, 5))
        self.assertTrue(preview_matches(fixture('preview'), board, move))
        self.assertFalse(preview_matches(fixture('score'), board, move))

    def test_reward_overlay_is_not_playable_and_has_full_bar(self):
        reward = fixture('reward')
        self.assertIsNone(read_board(reward))
        self.assertTrue(score_bar_full(reward))
        self.assertFalse(score_bar_full(fixture('score')))

    def test_unrelated_and_non_widescreen_frames_are_rejected(self):
        self.assertIsNone(read_board(canonical_frame(np.zeros((720, 1280, 3), np.uint8))))
        self.assertIsNone(canonical_frame(np.zeros((720, 1440, 3), np.uint8)))
