from src.char.BaseChar import BaseChar


class Youhu(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def has_long_actionbar(self):
        return True