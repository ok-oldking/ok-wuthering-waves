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

    def test_full_lines_include_but_do_not_remove_gray_blocks(self):
        corners = 0x8100000000000081
        mask = ROWS[0] | COLS[0] | corners | (1 << 9)
        self.assertEqual(clear_lines(mask, corners), (corners | (1 << 9), 2))

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
        for board_name, reward_name in (('score', 'reward'), ('score_4500', 'reward_4500')):
            with self.subTest(board=board_name):
                reward = fixture(reward_name)
                self.assertIsNone(read_board(reward))
                self.assertTrue(score_bar_full(reward))
                self.assertFalse(score_bar_full(fixture(board_name)))

    def test_reads_three_trays_and_all_four_gray_corners(self):
        board = read_board(fixture('score_4500'))
        self.assertEqual(board.mask, 0x991800C3C3001899)
        self.assertEqual(board.fixed, 0x8100000000000081)
        self.assertEqual([(p.slot, len(p.cells)) for p in board.pieces], [(0, 5), (1, 4), (2, 5)])
        move = choose_move(board)
        self.assertFalse(move.mask & board.mask)
        alternative = choose_move(board, excluded={(move.slot, move.mask)})
        self.assertNotEqual((alternative.slot, alternative.mask), (move.slot, move.mask))

    def test_partly_used_three_tray_layout_keeps_slot_ids(self):
        board = read_board(fixture('score_4500_partial'))
        self.assertEqual(board.mask, 0x9B1A3E0E3E001A9B)
        self.assertEqual(board.fixed, 0x8100000000000081)
        self.assertEqual([p.slot for p in board.pieces], [0, 1])

    def test_bright_piece_does_not_look_like_two_tray_divider(self):
        board = read_board(fixture('score_4500_ambiguous_trays'))
        self.assertIsNotNone(board)
        self.assertEqual([(piece.slot, len(piece.cells)) for piece in board.pieces], [(0, 9), (1, 4), (2, 5)])

    def test_unrelated_and_non_widescreen_frames_are_rejected(self):
        self.assertIsNone(read_board(canonical_frame(np.zeros((720, 1280, 3), np.uint8))))
        self.assertIsNone(canonical_frame(np.zeros((720, 1440, 3), np.uint8)))
