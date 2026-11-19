import re

from ok import BaseTask
from ok.device.interaction_methods.pynput import PynputInteraction

from src.task.rahai_blocks import (
    HEIGHT, WIDTH, canonical_frame, choose_move, clear_lines, preview_matches, read_board, score_bar_full,
)


class RahaiBlocksTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Rahai Blocks (Score Mode)"
        self.description = "Open the score board before starting. Keep the PC game in the foreground while the task plays."

    def _read_board(self):
        return read_board(canonical_frame(self.frame))

    def _score(self):
        texts = self.ocr(x=.09, y=.125, to_x=.235, to_y=.181)
        for box in texts:
            if match := re.search(r"(\d+)\s*[/／]\s*(\d+)", box.name):
                score, goal = map(int, match.groups())
                if goal > 0:
                    return score, goal
        return None

    def _finished(self, goal=None):
        if not score_bar_full(canonical_frame(self.frame)):
            return False
        if (score := self._score()) and score[0] >= (goal or score[1]):
            return True
        titles = self.ocr(x=.36, y=.216, to_x=.64, to_y=.29)
        return any(re.search(r"获\s*得|獲\s*得|Obtained|Rewards?|획득|Obtenido",
                             box.name, re.IGNORECASE) for box in titles)

    def _complete(self):
        self.log_info("Rahai Blocks target reached", notify=True)

    def _place(self, interaction, board, move):
        piece = next(p for p in board.pieces if p.slot == move.slot)
        height, width = self.frame.shape[:2]

        def point(xy):
            return round(xy[0] * width / WIDTH), round(xy[1] * height / HEIGHT)

        def move_cursor(xy):
            if not interaction.clickable():
                raise RuntimeError("Game lost foreground focus during a drag")
            interaction.move(*point(xy))

        source = piece.pickup
        dx, dy = move.drop
        move_cursor(source)
        self.sleep(.12)
        interaction.mouse_down(*point(source))
        release_at_target = False
        try:
            # Trigger the drag in the tray, but rotate over the board where
            # the game reliably accepts R even for pieces near the tray edge.
            self.sleep(.10)
            move_cursor((source[0] - 16, source[1]))
            self.sleep(.12)
            for i in range(1, 9):
                move_cursor((source[0] + (dx - source[0]) * i / 8, source[1] + (dy - source[1]) * i / 8))
                self.sleep(.025)
            self.sleep(.15)

            def rotate():
                if not interaction.clickable():
                    raise RuntimeError("Game lost foreground focus during a drag")
                interaction.send_key('r', down_time=.08)
                move_cursor((dx + 5, dy))
                self.sleep(.13)

            for _ in range(move.turns):
                rotate()
            # Retry a full rotation cycle if a key press was missed.
            for attempt in range(4):
                if attempt:
                    rotate()
                for ox, oy in ((0, 0), (0, -12), (-12, 0), (12, 0), (0, 12)):
                    move_cursor((dx + ox, dy + oy))
                    self.sleep(.16)
                    if interaction.clickable() and preview_matches(canonical_frame(self.next_frame()), board, move):
                        release_at_target = True
                        return True
            if not release_at_target:
                self.log_warning(f"Placement preview did not match: slot={move.slot}, turns={move.turns}, "
                                 f"row={move.row}, col={move.col}")
                self.screenshot("rahai_preview_mismatch")
            return release_at_target
        finally:
            if interaction.clickable():
                if not release_at_target:
                    # No task sleep here: cancellation must still release the button.
                    interaction.move(*point(source))
                interaction.mouse_up()
            else:
                # PynputInteraction.mouse_up deliberately skips when not focused.
                # Release our already-held button even if the focus changed.
                from pynput import mouse
                mouse.Controller().release(mouse.Button.left)

    def run(self):
        self.next_frame()
        frame = canonical_frame(self.frame)
        if frame is None:
            raise RuntimeError("Rahai Blocks requires a 16:9 PC game capture.")
        board = read_board(frame)
        score = self._score() if board and board.pieces else None
        if not score:
            if self._finished():
                self._complete()
                return
            if board is None:
                raise RuntimeError("Rahai Blocks board layout was not recognized. Open the score board and close any overlays.")
            if not board.pieces:
                raise RuntimeError("No pieces were visible in the Rahai Blocks trays. Wait for the next batch and try again.")
            raise RuntimeError("Rahai Blocks board was found, but the score and target could not be read.")
        if not self.hwnd or not self.hwnd.exists:
            raise RuntimeError("Rahai Blocks requires the native Windows PC client.")
        goal = score[1]
        if score[0] >= goal:
            self._complete()
            return
        interaction = PynputInteraction(self.executor.device_manager.capture_method, self.hwnd)
        self.hwnd.bring_to_front()
        self.sleep(.35)
        if not interaction.clickable():
            raise RuntimeError("Bring the PC game window to the foreground and start the task again.")
        misses = 0
        rejected = set()
        for _ in range(160):
            self.next_frame()
            board = self._read_board()
            if board is None or not board.pieces:
                self.sleep(.55)
                self.next_frame()
                board = self._read_board()
                if board is None or not board.pieces:
                    if self._finished(goal):
                        self._complete()
                        return
                    raise RuntimeError("The score board disappeared without a confirmed completion.")
            if not interaction.clickable():
                raise RuntimeError("Game lost foreground focus; no further moves were sent.")
            move = choose_move(board, excluded=rejected)
            if move is None:
                raise RuntimeError("No legal placement for the remaining pieces.")
            if not self._place(interaction, board, move):
                misses += 1
                rejected.add((move.slot, move.mask))
                if misses >= 3:
                    raise RuntimeError("Three placement previews did not match; stopped without dropping.")
                self.sleep(.35)
                continue
            misses = 0
            rejected.clear()
            expected, lines = clear_lines(board.mask | move.mask, board.fixed)
            self.log_info(f"Rahai Blocks: slot={move.slot + 1}, rotation={move.turns * 90}, "
                          f"cell=({move.row + 1},{move.col + 1}), lines={lines}")
            self.sleep(.95 if lines else .38)
            for _ in range(4):
                self.next_frame()
                actual = self._read_board()
                if actual and actual.mask == expected and actual.fixed == board.fixed:
                    if lines and self._finished(goal):
                        self._complete()
                        return
                    break
                self.sleep(.23)
            else:
                if lines and self._finished(goal):
                    self._complete()
                    return
                self.log_warning(f"Rahai Blocks: expected={expected:#018x}, "
                                 f"actual={hex(actual.mask) if actual else 'unrecognized'}")
                raise RuntimeError("Game did not confirm the predicted board after dropping the piece.")
        raise RuntimeError("Move limit reached without confirmed completion.")
