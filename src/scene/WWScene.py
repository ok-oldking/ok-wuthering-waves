from qfluentwidgets import FluentIcon

from ok import Logger, BaseScene

logger = Logger.get_logger(__name__)


class WWScene(BaseScene):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._in_team = None
        self._echo_enhance_btn = None
        self._in_combat = None

    def reset(self):
        self._in_team = None
        self._echo_enhance_btn = None
        self._in_combat = None

    def in_combat(self):
        return self._in_combat

    def set_in_combat(self):
        self._in_combat = True
        return True

    def set_not_in_combat(self):
        self._in_combat = False
        return False

    def in_team(self, fun):
        if self._in_team is None:
            self._in_team = fun()
        return self._in_team

    def echo_enhance_btn(self, fun):
        if self._echo_enhance_btn is None:
            self._echo_enhance_btn = fun()
        return self._echo_enhance_btn
