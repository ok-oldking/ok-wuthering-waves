from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Sequence

WARNING_TEXT = "**使用本工具存在封号风险。如果你不清楚自己在做什么，请不要使用。**"
DOWNLOAD_MIRRORS_SECTION = (
    "### 其他下载源 / Other download sources\n\n"
    "* [百度网盘](https://pan.baidu.com/s/102Mh1djq2B1T-cIJhct9Gg?pwd=okww) 免费下载\n"
    "* [夸克网盘](https://pan.quark.cn/s/80730a808d0e) 免费下载"
)
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


def extract_contributors_from_compare_payload(payload: dict) -> list[str]:
    """Extract unique non-bot GitHub logins from a GitHub compare API payload."""
    contributors: list[str] = []
    seen: set[str] = set()

    for commit in payload.get("commits") or []:
        if not isinstance(commit, dict):
            continue
        author = commit.get("author")
        if not isinstance(author, dict):
            continue
        login = (author.get("login") or "").strip()
        if not login or author.get("type") == "Bot" or login.endswith("[bot]"):
            continue
        key = login.casefold()
        if key not in seen:
            seen.add(key)
            contributors.append(login)

    return contributors


def fetch_contributors(
    repo: str,
    start_tag: str,
    end_tag: str,
    token: str = "",
    api_base: str = "https://api.github.com",
) -> list[str]:
    """Fetch unique contributor logins between two tags via the GitHub Compare API."""
    repo = repo.strip()
    start_tag = start_tag.strip()
    end_tag = end_tag.strip()
    if not repo or not start_tag or not end_tag or start_tag == end_tag:
        return []

    base = urllib.parse.quote(start_tag, safe="")
    head = urllib.parse.quote(end_tag, safe="")
    url = f"{api_base.rstrip('/')}/repos/{repo}/compare/{base}...{head}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ok-wuthering-waves-release-notes",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"Warning: failed to fetch contributors from {url}: {exc}", file=sys.stderr)
        return []

    if not isinstance(payload, dict):
        return []
    return extract_contributors_from_compare_payload(payload)


def format_contributors_section(contributors: Sequence[str]) -> str | None:
    """Format a Contributors markdown section with @mentions for GitHub release avatars."""
    mentions: list[str] = []
    seen: set[str] = set()
    for contributor in contributors:
        login = contributor.strip().lstrip("@")
        if not login:
            continue
        key = login.casefold()
        if key not in seen:
            seen.add(key)
            mentions.append(f"@{login}")

    if not mentions:
        return None
    return "### Contributors / 贡献者\n\n" + ", ".join(mentions)


def build_release_notes(
    tag: str,
    en_changelog: Path,
    zh_changelog: Path,
    fallback_changes: str = "",
    start_tag: str = "",
    end_tag: str = "",
    contributors: Sequence[str] = (),
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

    contributors_section = format_contributors_section(contributors)
    if contributors_section:
        sections.append(contributors_section)

    sections.append(DOWNLOAD_MIRRORS_SECTION)
    sections.append(INSTALL_FROM_SOURCE_SECTION)
    return "\n\n".join(sections) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GitHub release notes from changelogs.")
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG", ""), help="Release tag (e.g. v3.8.4)")
    parser.add_argument("--output", default="release_notes.md", help="Output markdown file path")
    parser.add_argument("--en-changelog", default="CHANGELOG.md", help="Path to English changelog")
    parser.add_argument("--zh-changelog", default="CHANGELOG.zh-CN.md", help="Path to Chinese changelog")
    args = parser.parse_args(argv)

    start_tag = os.environ.get("START_TAG", "")
    end_tag = os.environ.get("END_TAG", "") or args.tag
    contributors = fetch_contributors(
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
        start_tag=start_tag,
        end_tag=end_tag,
        token=os.environ.get("GITHUB_TOKEN", ""),
    )

    content = build_release_notes(
        tag=args.tag,
        en_changelog=Path(args.en_changelog),
        zh_changelog=Path(args.zh_changelog),
        fallback_changes=os.environ.get("FALLBACK_CHANGES", ""),
        start_tag=start_tag,
        end_tag=end_tag,
        contributors=contributors,
    )
    Path(args.output).write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
