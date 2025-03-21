from qfluentwidgets import FluentIcon

from ok import Logger, BaseScene
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


class WWScene(BaseScene):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._in_team = None
        self._echo_enhance_btn = None

    def reset(self):
        self._in_team = None
        self._echo_enhance_btn = None

    def in_team(self, fun):
        if self._in_team is None:
            self._in_team = fun()
        return self._in_team

    def echo_enhance_btn(self, fun):
        if self._echo_enhance_btn is None:
            self._echo_enhance_btn = fun()
        return self._echo_enhance_btn
