#!/usr/bin/env python3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import os
import requests

repo_full = os.getenv("GITHUB_REPOSITORY", "AliceJump/ok-wuthering-waves")

if "/" in repo_full:
    OWNER, REPO = repo_full.split("/", 1)
else:
    OWNER = "AliceJump"
    REPO = "ok-wuthering-waves"

TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

ASSETS_DIR = Path("assets")
OUTPUT_FILE = ASSETS_DIR / "downloads.svg"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "ok-wuthering-waves-download-stats",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def github_get(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def get_all_releases():
    page = 1
    releases = []

    while True:
        url = (
            f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
            f"?per_page=100&page={page}"
        )
        data = github_get(url)
        if not data:
            break
        releases.extend(data)
        page += 1

    return releases


def build_monthly_downloads(releases):
    monthly = defaultdict(int)

    for release in releases:
        published_at = release.get("published_at")
        if not published_at:
            continue

        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        month = dt.strftime("%Y-%m")

        downloads = sum(
            asset.get("download_count", 0)
            for asset in release.get("assets", [])
        )

        monthly[month] += downloads

    return sorted(monthly.items())


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_svg(items):
    width = 520
    header_height = 64
    row_height = 32
    padding_bottom = 18
    height = header_height + max(len(items), 1) * row_height + padding_bottom
    bar_x = 110
    bar_max_width = 340
    max_downloads = max((d for _, d in items), default=1)
    total_downloads = sum(d for _, d in items)
    colors = [
        "#2563eb",
        "#0ea5e9",
        "#06b6d4",
        "#14b8a6",
        "#22c55e",
        "#84cc16",
    ]
    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    svg.append('<rect width="100%" height="100%" rx="16" fill="#0b1220"/>')
    svg.append(
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" '
        f'rx="15" fill="none" stroke="#1f2937"/>'
    )
    svg.append(
        '<text x="24" y="38" fill="#e5e7eb" '
        'font-size="20" font-weight="700" '
        'font-family="Segoe UI, Arial">'
        'Monthly Downloads'
        '</text>'
    )
    svg.append(
        f'<text x="24" y="56" fill="#94a3b8" '
        f'font-size="12" font-family="Segoe UI, Arial">'
        f'{len(items)} months · {total_downloads:,} total downloads'
        '</text>'
    )
    y = 88
    for i, (month, downloads) in enumerate(items):
        percent = downloads / max_downloads if max_downloads else 0
        bar_width = max(2, int(percent * bar_max_width))
        color = colors[i % len(colors)]
        svg.append(
            f'<text x="24" y="{y}" fill="#e2e8f0" '
            f'font-size="13" font-family="Segoe UI, Arial">'
            f'{escape(month)}</text>'
        )
        svg.append(
            f'<text x="500" y="{y}" fill="#cbd5e1" '
            f'font-size="13" text-anchor="end" '
            f'font-family="Segoe UI, Arial">'
            f'{downloads:,}</text>'
        )
        svg.append(
            f'<rect x="{bar_x}" y="{y-10}" '
            f'width="{bar_max_width}" height="10" '
            f'rx="5" fill="#1f2937"/>'
        )
        svg.append(
            f'<rect x="{bar_x-4}" y="{y-10}" '
            f'width="{bar_width}" height="10" '
            f'rx="5" fill="{color}"/>'
        )
        y += row_height
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    releases = get_all_releases()
    items = build_monthly_downloads(releases)
    ASSETS_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(generate_svg(items), encoding="utf-8")
    print(f"generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()