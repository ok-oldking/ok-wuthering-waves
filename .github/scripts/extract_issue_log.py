#!/usr/bin/env python3
"""Safely extract diagnostic logs and screenshots from an OK-WW issue archive."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024
MAX_SCREENSHOTS_BYTES = 32 * 1024 * 1024
MAX_SCREENSHOT_COUNT = 40
MAX_SCREENSHOTS_TO_ANALYZE = 8
MAX_COMPRESSION_RATIO = 250
DOWNLOAD_TIMEOUT_SECONDS = 300
OUTPUT_ROOT = Path(".gh-aw/issue-logs")
LOG_OUTPUT_PATH = OUTPUT_ROOT / "logs" / "ok-script.log"
SCREENSHOTS_OUTPUT_PATH = OUTPUT_ROOT / "screenshots"
DIAGNOSTICS_OUTPUT_PATH = OUTPUT_ROOT / "diagnostics.json"
SCREENSHOTS_MANIFEST_OUTPUT_PATH = OUTPUT_ROOT / "screenshots-manifest.json"
SUPPORTED_SCREENSHOT_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp"}
APP_METADATA_PATTERN = re.compile(
    r"app_version:(?P<app_version>[^,\s]+)\s*,\s*"
    r"app_profile:(?P<app_profile>[^,]*?)\s*,\s*"
    r"pyappify_version:(?P<pyappify_version>[^,\s]+)"
)
PYAPPIFY_UPGRADEABLE_PATTERN = re.compile(
    r"pyappify_upgradeable:(?P<pyappify_upgradeable>True|False)"
)
DEVICE_WIDTH_PATTERN = re.compile(r"['\"]width['\"]\s*:\s*\**(?P<width>\d+)\**")
DEVICE_HEIGHT_PATTERN = re.compile(r"['\"]height['\"]\s*:\s*\**(?P<height>\d+)\**")


class UnsafeArchiveError(ValueError):
    """Raised when an issue attachment is not safe to process."""


def normalize_metadata_value(value: str) -> str | None:
    """Normalize formatting artifacts and unavailable metadata sentinels."""
    normalized = value.strip().replace("*", "")
    if normalized.casefold() in {"", "none", "null"}:
        return None
    return normalized


def validate_attachment_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = PurePosixPath(urllib.parse.unquote(parsed.path))
    parts = path.parts
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or len(parts) != 5
        or parts[:3] != ("/", "user-attachments", "files")
        or not parts[3].isdigit()
        or path.name.casefold() != "ok-ww-log.zip"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or parsed.port is not None
    ):
        raise UnsafeArchiveError(
            "expected an https://github.com/user-attachments/files/<id>/OK-WW-log.zip URL"
        )
    return url


def download_archive(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        validate_attachment_url(url),
        headers={"User-Agent": "OK-WW-issue-triage/1.0"},
    )
    deadline = time.monotonic() + DOWNLOAD_TIMEOUT_SECONDS
    with urllib.request.urlopen(request, timeout=10) as response, destination.open("wb") as output:
        final_url = urllib.parse.urlsplit(response.geturl())
        if final_url.scheme != "https" or final_url.hostname not in {
            "github.com",
            "objects.githubusercontent.com",
        }:
            raise UnsafeArchiveError("attachment redirected outside GitHub's file service")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_ARCHIVE_BYTES:
            raise UnsafeArchiveError("archive exceeds the 50 MiB download limit")

        remaining = MAX_ARCHIVE_BYTES + 1
        while remaining:
            if time.monotonic() >= deadline:
                raise UnsafeArchiveError("archive download exceeded the 300 second limit")
            chunk = response.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            output.write(chunk)
            remaining -= len(chunk)

        if destination.stat().st_size > MAX_ARCHIVE_BYTES:
            raise UnsafeArchiveError("archive exceeds the 50 MiB download limit")


def normalized_parts(info: zipfile.ZipInfo) -> tuple[str, ...]:
    path = PurePosixPath(info.filename.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise UnsafeArchiveError(f"archive contains an unsafe path: {info.filename}")
    return tuple(part for part in path.parts if part not in {"", "."})


def validate_member(info: zipfile.ZipInfo, label: str, maximum_size: int) -> None:
    if info.file_size > maximum_size:
        raise UnsafeArchiveError(f"{label} exceeds its extraction limit")
    if info.compress_size == 0 and info.file_size:
        raise UnsafeArchiveError(f"{label} has an invalid compressed size")
    if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
        raise UnsafeArchiveError(f"{label} has a suspicious compression ratio")


def select_log(archive: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, tuple[str, ...]]:
    matches = [
        (info, normalized_parts(info))
        for info in archive.infolist()
        if not info.is_dir()
        and tuple(part.casefold() for part in normalized_parts(info)[-2:])
        == ("logs", "ok-script.log")
    ]
    if not matches:
        raise UnsafeArchiveError("archive does not contain logs/ok-script.log")
    if len(matches) > 1:
        raise UnsafeArchiveError("archive contains multiple logs/ok-script.log files")

    log, parts = matches[0]
    validate_member(log, "logs/ok-script.log", MAX_LOG_BYTES)
    return log, parts[:-2]


def select_screenshots(
    archive: zipfile.ZipFile, archive_prefix: tuple[str, ...]
) -> list[tuple[zipfile.ZipInfo, tuple[str, ...]]]:
    screenshots: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
    seen_paths: set[str] = set()
    total_size = 0
    prefix_length = len(archive_prefix)
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = normalized_parts(info)
        if (
            len(parts) <= prefix_length + 1
            or tuple(part.casefold() for part in parts[:prefix_length])
            != tuple(part.casefold() for part in archive_prefix)
            or parts[prefix_length].casefold() != "screenshots"
        ):
            continue
        relative_parts = parts[prefix_length + 1 :]
        suffix = PurePosixPath(relative_parts[-1]).suffix.casefold()
        if suffix not in SUPPORTED_SCREENSHOT_SUFFIXES:
            continue
        relative_key = "/".join(relative_parts).casefold()
        if relative_key in seen_paths:
            raise UnsafeArchiveError("screenshots contains duplicate image paths")
        seen_paths.add(relative_key)
        validate_member(info, f"screenshot {info.filename}", MAX_SCREENSHOT_BYTES)
        total_size += info.file_size
        if total_size > MAX_SCREENSHOTS_BYTES:
            raise UnsafeArchiveError("screenshots exceed the 32 MiB extraction limit")
        screenshots.append((info, relative_parts))

    if len(screenshots) > MAX_SCREENSHOT_COUNT:
        raise UnsafeArchiveError("archive contains more than 40 screenshots")
    return screenshots


def has_valid_image_header(suffix: str, header: bytes) -> bool:
    return {
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    }[suffix]


def parse_log_diagnostics(log_path: Path) -> dict[str, object]:
    """Return metadata from the last matching application and device log lines."""
    diagnostics: dict[str, object] = {
        "app_version": None,
        "app_profile": None,
        "pyappify_version": None,
        "pyappify_upgradeable": None,
        "resolution": None,
        "source_lines": {
            "app_metadata": None,
            "device_manager": None,
        },
    }
    source_lines = diagnostics["source_lines"]
    assert isinstance(source_lines, dict)

    with log_path.open("r", encoding="utf-8", errors="replace") as log:
        for line_number, line in enumerate(log, start=1):
            app_match = APP_METADATA_PATTERN.search(line)
            if app_match:
                diagnostics.update(
                    {
                        key: normalize_metadata_value(value)
                        for key, value in app_match.groupdict().items()
                    }
                )
                upgradeable_match = PYAPPIFY_UPGRADEABLE_PATTERN.search(line)
                diagnostics["pyappify_upgradeable"] = (
                    upgradeable_match.group("pyappify_upgradeable") == "True"
                    if upgradeable_match
                    else None
                )
                source_lines["app_metadata"] = line_number

            if "DeviceManager:update_pc_device pc_device:" in line:
                width_match = DEVICE_WIDTH_PATTERN.search(line)
                height_match = DEVICE_HEIGHT_PATTERN.search(line)
                source_lines["device_manager"] = line_number
                if width_match and height_match:
                    diagnostics["resolution"] = {
                        "width": int(width_match.group("width")),
                        "height": int(height_match.group("height")),
                    }
                else:
                    diagnostics["resolution"] = None

    return diagnostics


def extract_archive(
    archive_path: Path, output_root: Path = OUTPUT_ROOT
) -> tuple[Path, list[Path]]:
    if not zipfile.is_zipfile(archive_path):
        raise UnsafeArchiveError("attachment is not a valid ZIP archive")

    with zipfile.ZipFile(archive_path) as archive:
        log, archive_prefix = select_log(archive)
        screenshots = select_screenshots(archive, archive_prefix)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="ok-ww-extracted-", dir=output_root.parent
        ) as staging_directory:
            staging_root = Path(staging_directory)
            staged_log = staging_root / "logs" / "ok-script.log"
            staged_log.parent.mkdir(parents=True)
            with archive.open(log) as source, staged_log.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            if staged_log.stat().st_size != log.file_size:
                raise UnsafeArchiveError("logs/ok-script.log size does not match ZIP metadata")
            diagnostics = parse_log_diagnostics(staged_log)
            (staging_root / "diagnostics.json").write_text(
                json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            analysis_candidates = sorted(
                screenshots,
                key=lambda item: (
                    item[0].date_time,
                    "/".join(item[1]).casefold(),
                ),
                reverse=True,
            )[:MAX_SCREENSHOTS_TO_ANALYZE]
            screenshot_manifest = {
                "total_extracted": len(screenshots),
                "analysis_limit": MAX_SCREENSHOTS_TO_ANALYZE,
                "analysis_candidates": [
                    str(PurePosixPath("screenshots", *relative_parts))
                    for _, relative_parts in analysis_candidates
                ],
            }
            (staging_root / "screenshots-manifest.json").write_text(
                json.dumps(screenshot_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            for screenshot, relative_parts in screenshots:
                staged_image = staging_root / "screenshots" / Path(*relative_parts)
                staged_image.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(screenshot) as source, staged_image.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                with staged_image.open("rb") as extracted_image:
                    header = extracted_image.read(12)
                suffix = staged_image.suffix.casefold()
                if not has_valid_image_header(suffix, header):
                    raise UnsafeArchiveError(
                        f"screenshot has invalid {suffix} content: {screenshot.filename}"
                    )

            if output_root.exists():
                shutil.rmtree(output_root)
            staging_root.replace(output_root)

    log_output = output_root / "logs" / "ok-script.log"
    screenshot_outputs = [
        output_root / "screenshots" / Path(*relative_parts)
        for _, relative_parts in screenshots
    ]
    return log_output, screenshot_outputs


def download_and_extract(
    url: str, output_root: Path = OUTPUT_ROOT
) -> tuple[Path, list[Path]]:
    # Never leave a previous issue's evidence available to a later triage run.
    if output_root.exists():
        shutil.rmtree(output_root)
    with tempfile.TemporaryDirectory(prefix="ok-ww-issue-log-") as directory:
        archive_path = Path(directory) / "OK-WW-log.zip"
        download_archive(url, archive_path)
        return extract_archive(archive_path, output_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="GitHub OK-WW-log.zip issue attachment URL")
    args = parser.parse_args()

    try:
        log_output, screenshots = download_and_extract(args.url)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, UnsafeArchiveError) as error:
        print(f"Could not extract issue log: {error}", file=sys.stderr)
        return 1

    print(
        f"Extracted {log_output} ({log_output.stat().st_size} bytes) "
        f"and {len(screenshots)} screenshot(s) to {SCREENSHOTS_OUTPUT_PATH}; "
        f"parsed metadata to {DIAGNOSTICS_OUTPUT_PATH}; "
        f"wrote the bounded review list to {SCREENSHOTS_MANIFEST_OUTPUT_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
