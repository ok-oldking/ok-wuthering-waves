# Crash diagnostics: pythonw has no console, so faulthandler writes fatal
# stacks to logs/ok-ww_fault.log (see faulthandler_setup.py).
import faulthandler_setup  # noqa: F401


if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()
