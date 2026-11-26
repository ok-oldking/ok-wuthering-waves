"""choose_move search-budget regression tests.

The original choose_move only pruned intermediate states when the tray had
exactly three pieces. Stages with four trays fell through to the unbounded
branch: a depth-2 search evaluates tens of millions of boards and hangs the
task for minutes. These tests pin the fix: four-tray searches return quickly
and the wall-clock budget yields the best move found so far.
"""

import time
import unittest

from src.task import rahai_blocks
from src.task.rahai_blocks import Board, choose_move


TRAY_4 = (
    ((0, 0), (0, 1), (0, 2), (0, 3)),   # I4
    ((0, 0), (1, 0), (2, 0), (2, 1)),   # L
    ((0, 0), (1, 0), (0, 1), (1, 1)),   # O
    ((0, 0), (0, 1), (0, 2)),           # I3
)


def make_pieces(shapes):
    pieces = []
    for slot, cells in enumerate(shapes):
        piece = type('P', (), {'slot': slot, 'cells': cells, 'pickup': (0, 0)})
        pieces.append(piece)
    return tuple(pieces)


class RahaiSearchBudgetTest(unittest.TestCase):

    def test_four_tray_search_finishes_quickly(self):
        board = Board(0, make_pieces(TRAY_4))
        start = time.monotonic()
        move = choose_move(board)
        elapsed = time.monotonic() - start
        self.assertIsNotNone(move, 'four-tray batch must produce a move')
        self.assertLess(elapsed, 5.0, f'choose_move took {elapsed:.1f}s (combinatorial blow-up)')

    def test_four_tray_on_crowded_board(self):
        # A crowded board has fewer legal placements but more intermediate
        # states, which is where the explosion is most likely.
        mask = 0
        for row in range(8):
            for col in range(8):
                if (row + col) % 3 == 0:
                    mask |= 1 << (row * 8 + col)
        board = Board(mask, make_pieces(TRAY_4))
        start = time.monotonic()
        choose_move(board)
        self.assertLess(time.monotonic() - start, 5.0)

    def test_time_budget_returns_best_so_far(self):
        saved = rahai_blocks.CHOOSE_MOVE_TIME_BUDGET
        rahai_blocks.CHOOSE_MOVE_TIME_BUDGET = 1e-9
        try:
            board = Board(0, make_pieces(TRAY_4))
            start = time.monotonic()
            move = choose_move(board)
            self.assertLess(time.monotonic() - start, 2.0, 'wall-clock fallback failed')
            self.assertIsNotNone(move, 'even with an exhausted budget a move must be returned')
        finally:
            rahai_blocks.CHOOSE_MOVE_TIME_BUDGET = saved

    def test_three_tray_still_works(self):
        board = Board(0, make_pieces(TRAY_4[:3]))
        self.assertIsNotNone(choose_move(board))


if __name__ == '__main__':
    unittest.main(verbosity=2)
