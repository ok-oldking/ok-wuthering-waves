# Task icons

Task and category icons use original transparent PNGs from
[555me/Wuthering-Waves-GameAssets](https://github.com/555me/Wuthering-Waves-GameAssets),
pinned to revision `a59e6fccfd7e04bc6470315737941609bc7b4acf`.
The original bytes, colors, dimensions, and alpha channels are preserved.
`sources.json` records each upstream path, source link, Git blob SHA, and SHA-256.
Game artwork belongs to its respective owners; this directory does not relicense it.

Most task symbols match the guidebook and function-menu artwork directly.
Related native symbols represent app-specific concepts: Friends for multiple
accounts, map switching for Fast Travel, the Bag for Auto Pick, and repair tools
for Diagnosis. Tacet Elimination uses the general activities symbol.
`login.svg` is an original fallback because automatic login has no corresponding
game-menu action icon in the inspected assets.

Tasks set `self.icon` and `self.group_icon` to absolute paths using
`src.task.task_icons`, which prefers PNGs and falls back to SVGs.
The existing emoji-prefixed `self.name` values remain gettext keys; ok-script's
task page removes that prefix from the displayed title and prefers `self.icon`
over the emoji tile. This preserves translations and saved task settings.

Daily Activities uses the native guidebook icon, Echo Management the echo-tuning symbol,
and Multi-account the Friends icon. `config.py` also supplies native All,
On-demand, and Triggers artwork through `task_category_icons`. The linked
ok-script UI accepts these overrides for filter tabs and section headings.

These are UI assets, not recognition templates. The `icons` directory is included
by `deploy.txt` in release updates. The task-list icons have no background tile.
The UI fits PNGs to their visible alpha bounds at render time so source padding
does not shrink individual symbols. Task glyphs are 28 px and category glyphs
20 px, with their aspect ratios and original asset bytes preserved.

`task_category_colors` in `config.py` gives each category a light/dark tint:
slate for All, teal for On-demand, rose for Triggers, blue for Daily Activities,
amber for Echo Management, and violet for Multi-account. Task icons inherit
their group's tint, or their task kind's tint when ungrouped. Tabs, section
headings, PNGs, and the login SVG use the same theme-aware renderer. Source
files are not recolored on disk.
