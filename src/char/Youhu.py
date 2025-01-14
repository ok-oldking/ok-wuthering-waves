from src.char.BaseChar import BaseChar


class Youhu(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)

    def has_long_actionbar(self):
        return True