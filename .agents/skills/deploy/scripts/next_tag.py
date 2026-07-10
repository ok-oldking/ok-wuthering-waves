#!/usr/bin/env python3
"""Calculate the next stable, beta, or alpha version tag."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass


STABLE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
PRERELEASE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-(alpha|beta)\.(\d+)$")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    def next_patch(self) -> "Version":
        return Version(self.major, self.minor, self.patch + 1)

    def tag(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, order=True)
class Prerelease:
    version: Version
    number: int


def repository_tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list", "v*"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def remote_tags(remote: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-remote", "--refs", "--tags", remote, "refs/tags/v*"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        ref.removeprefix("refs/tags/")
        for _, ref in (line.split("\t", 1) for line in result.stdout.splitlines())
    ]


def parse_tags(tags: list[str]) -> tuple[list[Version], dict[str, list[Prerelease]]]:
    stable: list[Version] = []
    prereleases: dict[str, list[Prerelease]] = {"alpha": [], "beta": []}
    for tag in tags:
        if match := STABLE_RE.fullmatch(tag.strip()):
            stable.append(Version(*(int(value) for value in match.groups())))
            continue
        if match := PRERELEASE_RE.fullmatch(tag.strip()):
            major, minor, patch, channel, number = match.groups()
            prereleases[channel].append(
                Prerelease(Version(int(major), int(minor), int(patch)), int(number))
            )
    return stable, prereleases


def next_tag(channel: str, tags: list[str]) -> str:
    stable, prereleases = parse_tags(tags)
    if not stable:
        raise ValueError("Cannot calculate a version tag without an existing stable vMAJOR.MINOR.PATCH tag.")

    latest_stable = max(stable)
    if channel == "release":
        return latest_stable.next_patch().tag()

    channel_tags = prereleases[channel]
    if channel_tags:
        latest_prerelease = max(channel_tags)
        if latest_prerelease.version > latest_stable:
            return (
                f"{latest_prerelease.version.tag()}-{channel}."
                f"{latest_prerelease.number + 1}"
            )

    return f"{latest_stable.next_patch().tag()}-{channel}.1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel", choices=("release", "beta", "alpha"))
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="Use an explicit existing tag instead of reading tags from the current git repository. Repeat as needed.",
    )
    parser.add_argument(
        "--remote",
        help="Include tag names published on this git remote, for example origin.",
    )
    args = parser.parse_args()

    try:
        tags = args.tags if args.tags is not None else repository_tags()
        if args.remote:
            tags.extend(remote_tags(args.remote))
        print(next_tag(args.channel, tags))
    except (subprocess.CalledProcessError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
