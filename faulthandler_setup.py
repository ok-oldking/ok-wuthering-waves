"""Enable faulthandler for crash diagnostics.

The packaged app runs as pythonw.exe which has no console, so fatal native
errors (e.g. access violations in graphics backends) used to kill the process
silently.  Importing this module writes every thread's Python stack to
logs/ok-ww_fault.log on such failures.
"""
import faulthandler
import os
import signal

_fault_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'ok-ww_fault.log')
try:
    os.makedirs(os.path.dirname(_fault_log), exist_ok=True)
    _fault_file = open(_fault_log, 'a', encoding='utf-8')
    faulthandler.enable(file=_fault_file)
    faulthandler.register(signal.SIGSEGV, file=_fault_file)
except Exception:
    try:
        faulthandler.enable()
    except Exception:
        pass
