"""Task-card artwork, kept separate from localized task names.

Original game PNGs are preferred, with SVGs for automation-specific fallbacks.
Resolve from this module so launchers can use any cwd without creating Qt objects.
"""

from pathlib import Path


_ICON_FOLDER = Path(__file__).resolve().parents[2] / 'icons' / 'tasks'
_ICON_ALIASES = {'category-echo': 'echo-tuning'}


def task_icon(name: str) -> str:
    name = _ICON_ALIASES.get(name, name)
    png = _ICON_FOLDER / f'{name}.png'
    return str(png if png.is_file() else _ICON_FOLDER / f'{name}.svg')
