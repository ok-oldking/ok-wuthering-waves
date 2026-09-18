"""Build the standalone Echo Score .okscript package."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile

from ok.core.script_packager import export_script


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SOURCE = ROOT / "packaging" / "echo_score"
FILES = (
    "echo_score.py",
    "xwuid_echo_data.py",
    "echo_stat_overlay.py",
    "overlay_status.py",
    "echo_score_settings.py",
    "echo_score_task.py",
)


def _copy_text(source: Path, target: Path, replacements=()):
    text = source.read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")


def build(output_folder=None, version="0.1.1"):
    output_folder = Path(output_folder or ROOT / "dist").resolve()
    with tempfile.TemporaryDirectory(prefix="echo-score-okscript-") as temp:
        stage = Path(temp)
        _copy_text(
            ROOT / "src" / "echo_score.py", stage / "echo_score.py",
            (("from src.xwuid_echo_data import TEMPLATES", "from xwuid_echo_data import TEMPLATES"),),
        )
        shutil.copy2(ROOT / "src" / "xwuid_echo_data.py", stage / "xwuid_echo_data.py")
        _copy_text(
            ROOT / "src" / "gui" / "EchoStatOverlay.py", stage / "echo_stat_overlay.py",
            (("from src.echo_score import", "from echo_score import"),),
        )
        _copy_text(
            ROOT / "src" / "gui" / "OverlayStatus.py", stage / "overlay_status.py",
            (("paint_okww_status", "paint_echo_status"),),
        )
        shutil.copy2(PACKAGE_SOURCE / "echo_score_task.py", stage / "echo_score_task.py")
        shutil.copy2(PACKAGE_SOURCE / "echo_score_settings.py", stage / "echo_score_settings.py")
        shutil.copy2(PACKAGE_SOURCE / "README.md", stage / "README.md")
        success, message, output_path = export_script(
            list(FILES), "echo-score", "声骸评分", version,
            task_folder=str(stage), output_folder=str(output_folder),
        )
        if not success:
            raise RuntimeError(message)
        return Path(output_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default="0.1.1")
    args = parser.parse_args()
    print(build(args.output, args.version))


if __name__ == "__main__":
    main()
