"""Vision and move planning for the 8x8 two-tray score board."""

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np


WIDTH, HEIGHT = 2048, 1152
SIZE = 8
BOARD_X, BOARD_Y, CELL = 537.5, 89.4, 121.65
TRAY_X, TRAY_Y, TILE = 1785.5, (495, 735), 38.3
ROWS = tuple(255 << (SIZE * r) for r in range(SIZE))
COLS = tuple(0x0101010101010101 << c for c in range(SIZE))
FULL = (1 << (SIZE * SIZE)) - 1


@dataclass(frozen=True)
class Piece:
    slot: int
    cells: tuple
    pickup: tuple


@dataclass(frozen=True)
class Move:
    slot: int
    turns: int
    row: int
    col: int
    cells: tuple
    mask: int

    @property
    def drop(self):
        width = max(x for x, _ in self.cells) + 1
        height = max(y for _, y in self.cells) + 1
        return (BOARD_X + (self.col + width / 2) * CELL,
                BOARD_Y + (self.row + height / 2) * CELL)


@dataclass(frozen=True)
class Board:
    mask: int
    pieces: tuple


def canonical_frame(frame):
    if frame is None or abs(frame.shape[1] / frame.shape[0] - 16 / 9) > 0.012:
        return None
    return cv2.resize(frame[:, :, :3], (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def _value(frame, x, y, radius=7):
    x, y = round(x), round(y)
    return float(np.median(frame[y-radius:y+radius+1, x-radius:x+radius+1].max(axis=2)))


def board_mask(frame):
    """Vote across each tile so the floating rotation hint is not a tile."""
    centers_x = BOARD_X + (np.arange(SIZE) + .5) * CELL
    centers_y = BOARD_Y + (np.arange(SIZE) + .5) * CELL
    votes = np.zeros((SIZE, SIZE), dtype=np.uint8)
    for dx, dy in ((-24, -25), (24, -25), (-24, 25), (24, 25)):
        x = np.rint(centers_x + dx).astype(int)
        y = np.rint(centers_y + dy).astype(int)
        colors = frame[y[:, None], x[None, :]]
        bright = colors.max(axis=2)
        votes += (bright > 88) & (bright - colors.min(axis=2) > 40)
    return sum(1 << int(i) for i in np.flatnonzero(votes.ravel() >= 3))


def _read_piece(frame, slot):
    cy = TRAY_Y[slot]
    x0, y0 = round(TRAY_X) - 88, cy - 88
    crop = frame[y0:cy+88, x0:x0+176]
    bright = crop.max(axis=2) > 105
    ys, xs = np.where(bright)
    if len(xs) < 20:
        return None
    if len(xs) < 800:
        raise ValueError("Tray contains a partial tile")
    w, h = round((xs.max() - xs.min() + 1) / TILE), round((ys.max() - ys.min() + 1) / TILE)
    if not (1 <= w <= 5 and 1 <= h <= 5):
        raise ValueError("Tray piece dimensions are invalid")
    cx = x0 + (int(xs.max()) + int(xs.min())) / 2
    center_y = y0 + (int(ys.max()) + int(ys.min())) / 2
    if abs(cx - TRAY_X) > 5 or abs(center_y - cy) > 5:
        raise ValueError("Tray piece is not centered")
    points = {(x, y): (cx + (x - (w - 1) / 2) * TILE, center_y + (y - (h - 1) / 2) * TILE)
              for y in range(h) for x in range(w)}
    cells = tuple(sorted(p for p, (x, y) in points.items() if _value(frame, x, y) > 83))
    if not cells or max(x for x, _ in cells) != w - 1 or max(y for _, y in cells) != h - 1:
        raise ValueError("Tray piece was only partially recognized")
    reached = {cells[0]}
    while neighbors := {p for p in cells if p not in reached and
                         any(abs(p[0] - x) + abs(p[1] - y) == 1 for x, y in reached)}:
        reached.update(neighbors)
    if len(reached) != len(cells) or not 900 * len(cells) <= len(xs) <= 1580 * len(cells):
        raise ValueError("Tray pixels do not match an intact piece")
    pickup = min((points[p] for p in cells), key=lambda p: (p[0] - cx)**2 + (p[1] - center_y)**2)
    return Piece(slot, cells, pickup)


def read_board(frame):
    if frame is None:
        return None
    # Confirm the event icon, upper grid border and both dark tray interiors.
    icon = frame[44:102, 50:110]
    if np.count_nonzero(icon.min(axis=2) > 181) < 210:
        return None
    if not (_value(frame, 1024, 73, 3) - _value(frame, 1024, 85, 2) > 45 and
            all(_value(frame, 1704, y - 82, 3) < 65 for y in TRAY_Y)):
        return None
    try:
        pieces = tuple(p for slot in range(len(TRAY_Y)) if (p := _read_piece(frame, slot)) is not None)
    except ValueError:
        return None
    return Board(board_mask(frame), pieces)


def clear_lines(mask):
    lines = [line for line in (*ROWS, *COLS) if mask & line == line]
    for line in lines:
        mask &= ~line
    return mask, len(lines)


@lru_cache(maxsize=128)
def placements(cells):
    result, seen = [], set()
    for turns in range(4):
        if cells not in seen:
            seen.add(cells)
            w = max(x for x, _ in cells) + 1
            h = max(y for _, y in cells) + 1
            for r in range(SIZE - h + 1):
                for c in range(SIZE - w + 1):
                    mask = sum(1 << ((r + y) * SIZE + c + x) for x, y in cells)
                    result.append((turns, r, c, cells, mask))
        bottom = max(y for _, y in cells)
        cells = tuple(sorted((bottom - y, x) for x, y in cells))
    return tuple(result)


@lru_cache(maxsize=65536)
def board_value(mask):
    empty = FULL ^ mask
    left, right = COLS[0], COLS[-1]
    horizontal = empty & (empty >> 1) & ~right
    squares = (horizontal & (horizontal >> SIZE)).bit_count()
    isolated = empty & ~((empty << SIZE) | (empty >> SIZE) |
                         ((empty & ~right) << 1) | ((empty & ~left) >> 1))
    near = sum(max(0, (mask & line).bit_count() - 4)**2 for line in (*ROWS, *COLS))
    return 2 * squares + near - 12 * isolated.bit_count() - 2 * mask.bit_count()


def choose_move(board, excluded=()):
    """Search both orders and all rotations of the currently visible batch."""
    best, best_rank = None, None
    for piece in board.pieces:
        rest = next((p for p in board.pieces if p.slot != piece.slot), None)
        for move in (Move(piece.slot, *p) for p in placements(piece.cells)):
            if move.mask & board.mask or (move.slot, move.mask) in excluded:
                continue
            after, lines = clear_lines(board.mask | move.mask)
            # Simultaneous clears are worth more than the same number across moves.
            score = lines * (lines + 1) * 30
            if rest is None:
                future = board_value(after)
            else:
                future = max((n * (n + 1) * 30 + board_value(final)
                              for *_, mask in placements(rest.cells) if not mask & after
                              for final, n in [clear_lines(after | mask)]), default=-10000)
            rank = (score + future, lines, -move.turns)
            if best_rank is None or rank > best_rank:
                best, best_rank = move, rank
    return best


def preview_matches(frame, board, move):
    # A matching footprint requires one new occupied cell per tile in the move.
    return frame is not None and board_mask(frame) == (board.mask | move.mask)


def score_bar_full(frame):
    """The far end stays magenta even under the darkened rewards overlay."""
    if frame is None:
        return False
    pixels = frame[194:215, 459:470].astype(np.int16)
    return bool(np.median(pixels[:, :, 2] - pixels[:, :, 1]) >= 6 and
                np.median(pixels[:, :, 0] - pixels[:, :, 1]) >= 6)
