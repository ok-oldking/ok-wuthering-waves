"""Build the portable Echo Score .okscript package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from ok.core.script_packager import export_script


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SOURCE = ROOT / "packaging" / "echo_score"
FILES = (
    "echo_score.py", "xwuid_echo_data.py", "echo_stat_overlay.py",
    "overlay_status.py", "echo_score_settings.py", "echo_score_task.py",
)
IMPORT_FILES = FILES + ("README.md", "manifest.json")


def _copy_text(source, target, replacements=()):
    text = Path(source).read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    Path(target).write_text(text, encoding="utf-8")


def _stage_package(stage):
    _copy_text(ROOT / "src" / "echo_score.py", stage / "echo_score.py",
               (("from src.xwuid_echo_data import TEMPLATES", "from xwuid_echo_data import TEMPLATES"),))
    shutil.copy2(ROOT / "src" / "xwuid_echo_data.py", stage / "xwuid_echo_data.py")
    _copy_text(ROOT / "src" / "gui" / "EchoStatOverlay.py", stage / "echo_stat_overlay.py",
               (("from src.echo_score import", "from echo_score import"),))
    _copy_text(ROOT / "src" / "gui" / "OverlayStatus.py", stage / "overlay_status.py")
    for name in ("echo_score_settings.py", "echo_score_task.py", "README.md"):
        shutil.copy2(PACKAGE_SOURCE / name, stage / name)


def build(output_folder=None, version="0.2.0"):
    output_folder = Path(output_folder or ROOT / "dist").resolve()
    output_folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="echo-score-okscript-") as temp:
        stage = Path(temp)
        _stage_package(stage)
        success, message, output_path = export_script(
            list(FILES), "echo-score", "声骸评分", version,
            task_folder=str(stage), output_folder=str(output_folder),
        )
        if not success:
            raise RuntimeError(message)
        return Path(output_path)


def build_import_folder(output_folder=None, version="0.2.0"):
    """Create the folder copied directly to OKWW's ``ok/_import`` directory."""
    output = Path(output_folder or ROOT / "dist" / "echo-score").resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="echo-score-import-") as temp:
        stage = Path(temp)
        _stage_package(stage)
        (stage / "manifest.json").write_text(json.dumps({
            "file_name": "echo-score",
            "script_name": "声骸评分",
            "version": version,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        for name in IMPORT_FILES:
            shutil.copy2(stage / name, output / name)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default="0.2.0")
    parser.add_argument("--folder", action="store_true", help="also build a direct _import folder")
    args = parser.parse_args()
    print(build(args.output, args.version))
    if args.folder:
        print(build_import_folder(args.output / "echo-score", args.version))
