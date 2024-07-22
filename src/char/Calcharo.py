from typing import Any

from src.char.BaseChar import BaseChar


class Calcharo(BaseChar):

    def switch_next_char(self, *args: Any, **kwargs: Any):
        if self.is_con_full():
            self.task.in_liberation = True
        super().switch_next_char(*args, **kwargs)
