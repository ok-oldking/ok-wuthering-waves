from __future__ import annotations

import argparse
import os
from pathlib import Path

WARNING_TEXT = "**使用本工具存在封号风险。如果你不清楚自己在做什么，请不要使用。**"
INSTALL_FROM_SOURCE_SECTION = (
    "### Install from source\n\n"
    "See the [source installation guide]"
    "(https://github.com/ok-oldking/ok-wuthering-waves/blob/master/docs/development/contributing.md)."
)


def _normalize_version_token(token: str) -> str:
    cleaned = token.strip().strip("[]")
    return cleaned[1:] if cleaned.startswith("v") else cleaned


def extract_changelog_section(changelog_text: str, tag: str) -> str | None:
    """Extract the markdown body for a specific version tag from a changelog."""
    target = _normalize_version_token(tag)
    if not target:
        return None

    lines = changelog_text.splitlines()
    capturing = False
    captured: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if capturing:
                break
            rest = line[3:].strip()
            if not rest:
                continue
            token = rest.split(maxsplit=1)[0]
            if _normalize_version_token(token) == target:
                capturing = True
            continue

        if capturing:
            if line.startswith("# "):
                break
            captured.append(line)

    if not capturing:
        return None

    body = "\n".join(captured).strip()
    return body or None


def read_changelog_section(path: Path, tag: str) -> str | None:
    if not path.is_file():
        return None
    return extract_changelog_section(path.read_text(encoding="utf-8"), tag)


def build_release_notes(
    tag: str,
    en_changelog: Path,
    zh_changelog: Path,
    fallback_changes: str = "",
    start_tag: str = "",
    end_tag: str = "",
) -> str:
    """Build GitHub release notes from English and Chinese changelogs."""
    sections: list[str] = [WARNING_TEXT]

    en_notes = read_changelog_section(en_changelog, tag)
    zh_notes = read_changelog_section(zh_changelog, tag)

    if en_notes:
        sections.append(f"### Changelog (English)\n\n{en_notes}")
    if zh_notes:
        sections.append(f"### 更新日志 (中文)\n\n{zh_notes}")

    if not en_notes and not zh_notes and fallback_changes.strip():
        header = "### 更新日志"
        if start_tag or end_tag:
            header = f"### 更新日志 {start_tag} -> {end_tag}".strip()
        sections.append(f"{header}\n\n{fallback_changes.strip()}")

    sections.append(INSTALL_FROM_SOURCE_SECTION)
    return "\n\n".join(sections) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GitHub release notes from changelogs.")
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG", ""), help="Release tag (e.g. v3.8.4)")
    parser.add_argument("--output", default="release_notes.md", help="Output markdown file path")
    parser.add_argument("--en-changelog", default="CHANGELOG.md", help="Path to English changelog")
    parser.add_argument("--zh-changelog", default="CHANGELOG.zh-CN.md", help="Path to Chinese changelog")
    args = parser.parse_args(argv)

    content = build_release_notes(
        tag=args.tag,
        en_changelog=Path(args.en_changelog),
        zh_changelog=Path(args.zh_changelog),
        fallback_changes=os.environ.get("FALLBACK_CHANGES", ""),
        start_tag=os.environ.get("START_TAG", ""),
        end_tag=os.environ.get("END_TAG", ""),
    )
    Path(args.output).write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
