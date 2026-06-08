import os
import subprocess
import sys
from pathlib import Path


def relaunch_with_project_venv():
    project_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    if not project_python.exists():
        return

    current_python = Path(sys.executable).resolve()
    if current_python == project_python.resolve():
        return

    env = os.environ.copy()
    env["OK_WW_RELAUNCHED"] = "1"
    subprocess.run([str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
    raise SystemExit


if os.environ.get("OK_WW_RELAUNCHED") != "1":
    relaunch_with_project_venv()


if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()
