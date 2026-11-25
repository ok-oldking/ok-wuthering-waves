"""Vision and move planning for the 8x8 score board."""

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np


WIDTH, HEIGHT = 2048, 1152
SIZE = 8
BOARD_X, BOARD_Y, CELL = 537.5, 89.4, 121.65
TRAY_X, TILE = 1785.5, 38.3
TRAY_LAYOUTS = ((495, 735), (375, 615, 855), (255, 495, 735, 975))
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
    fixed: int = 0


def canonical_frame(frame):
    if frame is None or abs(frame.shape[1] / frame.shape[0] - 16 / 9) > 0.012:
        return None
    return cv2.resize(frame[:, :, :3], (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def _value(frame, x, y, radius=7):
    x, y = round(x), round(y)
    return float(np.median(frame[y-radius:y+radius+1, x-radius:x+radius+1].max(axis=2)))


def _board_masks(frame):
    """Vote across each tile so the floating rotation hint is not a tile."""
    centers_x = BOARD_X + (np.arange(SIZE) + .5) * CELL
    centers_y = BOARD_Y + (np.arange(SIZE) + .5) * CELL
    votes = np.zeros((SIZE, SIZE), dtype=np.uint8)
    fixed_votes = np.zeros_like(votes)
    for dx, dy in ((-24, -25), (24, -25), (-24, 25), (24, 25)):
        x = np.rint(centers_x + dx).astype(int)
        y = np.rint(centers_y + dy).astype(int)
        colors = frame[y[:, None], x[None, :]]
        bright = colors.max(axis=2)
        chroma = bright - colors.min(axis=2)
        fixed = (bright >= 80) & (bright <= 155) & (chroma <= 15)
        votes += ((bright > 88) & (chroma > 40)) | fixed
        fixed_votes += fixed
    return tuple(sum(1 << int(i) for i in np.flatnonzero(v.ravel() >= 3)) for v in (votes, fixed_votes))


def _read_piece(frame, slot, cy):
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
    # Confirm the event icon and upper grid border.
    icon = frame[44:102, 50:110]
    if np.count_nonzero(icon.min(axis=2) > 181) < 210:
        return None
    # Scan for the border's bright-to-dark drop instead of sampling fixed points:
    # a few pixels of vertical drift would otherwise reject a valid board.
    border_x = 1024
    best_drop = 0.0
    for y in range(66, 92):
        above = _value(frame, border_x, y, 3)
        below = _value(frame, border_x, y + 8, 2)
        best_drop = max(best_drop, above - below)
    if best_drop <= 45:
        return None
    # Check both the dark tray interiors and the bright gaps between them.
    # The interior samples alone can accidentally land in neighboring trays.
    layouts = [layout for layout in TRAY_LAYOUTS if
               all(_value(frame, 1710, cy + dy, 3) < 65 for cy in layout for dy in (-82, 82))
               and all(_value(frame, 1710, (a + b) // 2, 3) > 105 for a, b in zip(layout, layout[1:]))]
    # The two-tray layout is the middle of the four-tray one; keep the larger match.
    layouts = [layout for layout in layouts if not any(set(layout) < set(other) for other in layouts)]
    trays = []
    for layout in layouts:
        try:
            pieces = tuple(piece for slot, cy in enumerate(layout)
                           if (piece := _read_piece(frame, slot, cy)) is not None)
        except ValueError:
            # A bright piece in a three-tray board can look like a divider
            # in the two-tray layout. Reject layouts with off-center pieces.
            continue
        trays.append(pieces)
    if len(trays) != 1:
        return None
    mask, fixed = _board_masks(frame)
    return Board(mask, trays[0], fixed)


def clear_lines(mask, fixed=0):
    """Gray blocks contribute to full lines but stay in place when cleared."""
    lines = [line for line in (*ROWS, *COLS) if mask & line == line]
    for line in lines:
        mask &= ~line
    return mask | fixed, len(lines)


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
    """Search the current batch; bound intermediate states for three trays."""
    batch = {p.slot: placements(p.cells) for p in board.pieces}
    states = [(board.mask, tuple(batch), 0, 0, None)]
    best = None
    for depth in range(len(batch)):
        candidates = {}
        for mask, remaining, score, first_lines, first in states:
            for slot in remaining:
                rest = tuple(s for s in remaining if s != slot)
                for p in batch[slot]:
                    tile_mask = p[-1]
                    if tile_mask & mask or (first is None and (slot, tile_mask) in excluded):
                        continue
                    after, lines = clear_lines(mask | tile_mask, board.fixed)
                    total = score + lines * (lines + 1) * 30
                    move = first or Move(slot, *p)
                    initial = first_lines if first else lines
                    rank = (total + board_value(after), initial, -move.turns)
                    key = (after, rest)
                    if key not in candidates or rank > candidates[key][0]:
                        candidates[key] = (rank, (after, rest, total, initial, move))
        if not candidates:
            break
        ordered = sorted(candidates.values(), key=lambda candidate: candidate[0], reverse=True)
        best = ordered[0][1][-1]
        # Preserve alternatives for every remaining subset before the final ply.
        if len(batch) == 3 and depth < 2:
            counts = {}
            states = []
            for _, state in ordered:
                rest = state[1]
                if counts.get(rest, 0) < 24:
                    states.append(state)
                    counts[rest] = counts.get(rest, 0) + 1
        else:
            states = [state for _, state in ordered]
    return best


def preview_matches(frame, board, move):
    # A matching footprint requires one new occupied cell per tile in the move.
    return frame is not None and _board_masks(frame) == (board.mask | move.mask, board.fixed)


def score_bar_full(frame):
    """The far end stays magenta even under the darkened rewards overlay."""
    if frame is None:
        return False
    pixels = frame[194:215, 459:470].astype(np.int16)
    return bool(np.median(pixels[:, :, 2] - pixels[:, :, 1]) >= 6 and
                np.median(pixels[:, :, 0] - pixels[:, :, 1]) >= 6)
