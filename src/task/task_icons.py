"""Task-card artwork, kept separate from localized task names.

Original game PNGs are used unless a crisp SVG replacement is available.
Resolve from this module so launchers can use any cwd without creating Qt objects.
"""

from pathlib import Path


_ICON_FOLDER = Path(__file__).resolve().parents[2] / 'icons' / 'tasks'
_ICON_ALIASES = {'category-echo': 'echo-tuning'}


def task_icon(name: str) -> str:
    name = _ICON_ALIASES.get(name, name)
    svg = _ICON_FOLDER / f'{name}.svg'
    return str(svg if svg.is_file() else _ICON_FOLDER / f'{name}.png')
