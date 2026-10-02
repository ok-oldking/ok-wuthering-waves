"""Add selected XW-UID calc.json templates to the bundled score snapshot.

Example::

    python scripts/update_xwuid_echo_templates.py E:/xwuid-score-resources 1311 1312
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import subprocess
import zlib

from src.xwuid_echo_data import CONDITIONS, TEMPLATES


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_PATH = Path("XutheringWavesUID/resource/map/character")


def update(resource_root: Path, character_ids: list[str]) -> None:
    source_commit = subprocess.check_output(
        ["git", "-C", str(resource_root), "rev-parse", "HEAD"], text=True
    ).strip()
    templates = dict(TEMPLATES)
    for character_id in character_ids:
        character_dir = resource_root / RESOURCE_PATH / character_id
        calc_files = sorted(character_dir.glob("calc*.json"))
        if not calc_files:
            raise FileNotFoundError(f"No calc*.json files in {character_dir}")
        variants = {}
        for calc_file in calc_files:
            variant = "default" if calc_file.name == "calc.json" else calc_file.stem.removeprefix("calc-")
            template = json.loads(calc_file.read_text(encoding="utf-8"))
            if not isinstance(template, dict) or not isinstance(template.get("name"), str):
                raise ValueError(f"Invalid template: {calc_file}")
            variants[variant] = template
        templates[character_id] = variants
        print(f"{character_id}: {', '.join(item['name'] for item in variants.values())}")

    data = json.dumps(
        {"templates": templates, "conditions": CONDITIONS},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    encoded = base64.b85encode(zlib.compress(data, level=9)).decode("ascii")
    output = ROOT / "src" / "xwuid_echo_data.py"
    output.write_bytes((
        '"""Compressed snapshot of XW-UID echo templates.\n\n'
        f'Source: https://cnb.cool/loping151/XutheringWavesUID-Resources\n'
        f'Commit: {source_commit}\n'
        f'Updated character IDs: {", ".join(character_ids)}\n'
        'Other character templates and conditions remain from the prior snapshot.\n'
        '"""\n\n'
        'from __future__ import annotations\n\n'
        'import base64\nimport json\nimport zlib\n\n'
        f'SOURCE_COMMIT = "{source_commit}"\n'
        f'_ENCODED = r"""{encoded}"""\n\n'
        '_DATA = json.loads(zlib.decompress(base64.b85decode(_ENCODED)).decode("utf-8"))\n'
        'TEMPLATES = _DATA["templates"]\nCONDITIONS = _DATA["conditions"]\n'
    ).encode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource_root", type=Path)
    parser.add_argument("character_ids", nargs="+", help="XW-UID numeric character IDs")
    args = parser.parse_args()
    update(args.resource_root.resolve(), args.character_ids)
