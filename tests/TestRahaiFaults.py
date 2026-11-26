"""Fault-block (故障方块) vision and simulation tests.

Negative fixtures are the real stage screenshots already in tests/images.
The positive fixture is derived from a real board by painting the fault-block
colour measured from the in-game tutorial art (BGR ~ 242, 105, 207); no
synthetic flat-black board is used.
"""
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.task.rahai_blocks import (
    BOARD_X, BOARD_Y, CELL, ROWS, SIZE, Board, _board_masks, _fault_mask,
    canonical_frame, choose_move, clear_lines, read_board,
)


def fixture(name):
    path = Path(__file__).with_name('images') / f'rahai_{name}.jpg'
    return canonical_frame(cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR))


class TestRahaiFaults(unittest.TestCase):

    def test_ordinary_magenta_blocks_in_real_stages_are_not_faults(self):
        """Regression: rahai_score.jpg had two ordinary blocks at (2,5),(2,6)
        misread as faults by the old r>160/b>170 threshold, which changed the
        planner's move from (0,2,5) to (0,6,5)."""
        for name in ('score', 'score_4500', 'score_4500_partial',
                     'score_4500_ambiguous_trays', 'four_trays_outer', 'preview'):
            with self.subTest(stage=name):
                frame = fixture(name)
                mask, _ = _board_masks(frame)
                self.assertEqual(_fault_mask(frame, mask), 0)

    def test_fault_static_is_detected_on_real_board_background(self):
        """Positive: paint two cells with the tutorial-art fault static over a
        real board, and require exactly those two cells to be recognised."""
        frame = fixture('score')
        rng = np.random.default_rng(7)
        half = 55
        expected = 0
        for row, col in ((2, 3), (2, 5)):
            cx = round(BOARD_X + (col + .5) * CELL)
            cy = round(BOARD_Y + (row + .5) * CELL)
            tile = frame[cy - half:cy + half, cx - half:cx + half]
            tile[:, :, 0] = rng.integers(220, 256, tile.shape[:2])
            tile[:, :, 1] = rng.integers(85, 155, tile.shape[:2])
            tile[:, :, 2] = rng.integers(185, 256, tile.shape[:2])
            expected |= 1 << (row * SIZE + col)
        mask, _ = _board_masks(frame)
        self.assertEqual(_fault_mask(frame, mask), expected)

    def test_faulted_blocks_fill_lines_but_survive(self):
        fault = 1 << 9
        row = ROWS[1] & ~fault
        after, lines = clear_lines(row, 0, fault)
        self.assertEqual(lines, 1)
        self.assertEqual(after, fault)

    def test_solver_accounts_for_faulted_blocks(self):
        fault = 1 << 0 | 1 << 1
        pieces = (type('P', (), {'slot': 0,
                                 'cells': ((0, 0), (0, 1), (0, 2), (0, 3)),
                                 'pickup': (0, 0)}),)
        board = Board(mask=ROWS[0] ^ fault, pieces=pieces, fixed=0, fault=fault)
        move = choose_move(board)
        self.assertIsNotNone(move)
        after, lines = clear_lines(board.mask | move.mask, board.fixed, board.fault)
        self.assertGreaterEqual(lines, 1)
        self.assertEqual(after & fault, fault)

    def test_real_stage_move_choice_is_unchanged(self):
        board = read_board(fixture('score'))
        self.assertEqual(board.fault, 0)
        move = choose_move(board)
        self.assertEqual((move.slot, move.row, move.col), (0, 2, 5))


if __name__ == '__main__':
    unittest.main()
