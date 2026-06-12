import importlib
import sys


if sys.platform == "win32":
    _win32api = importlib.import_module("win32api")
    GetCursorPos = _win32api.GetCursorPos
    SetCursorPos = _win32api.SetCursorPos
else:
    try:
        import Quartz
    except ImportError:
        Quartz = None

    def _require_quartz():
        if Quartz is None:
            raise RuntimeError("Quartz is required for cursor operations on this platform")

    def GetCursorPos():
        _require_quartz()
        location = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return int(location.x), int(location.y)

    def SetCursorPos(position):
        _require_quartz()
        x, y = position
        Quartz.CGWarpMouseCursorPosition((float(x), float(y)))
        Quartz.CGAssociateMouseAndMouseCursorPosition(True)
