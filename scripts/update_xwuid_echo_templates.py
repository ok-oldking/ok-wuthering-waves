"""Fetch all XW-UID Echo weights, optionally test, package, sync and publish.

Run with --check to compare only, or --publish --commit-push for the full release.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPOSITORY = "https://cnb.cool/loping151/XutheringWavesUID-Resources"
RESOURCE_PATH = "XutheringWavesUID/resource/map/character"
SNAPSHOT = ROOT / "src" / "xwuid_echo_data.py"
SPARSE_PATTERNS = f"/{RESOURCE_PATH}/*/calc*.json\n/{RESOURCE_PATH}/*/condition.json\n"


def git(repo, *args, input_text=None):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], input=input_text, text=True, encoding="utf-8"
    ).strip()


def require_clean(repo):
    if git(repo, "status", "--porcelain"):
        raise RuntimeError(f"Repository has local changes; commit them first: {repo}")


def push_target(repo):
    branch = git(repo, "symbolic-ref", "--short", "HEAD")
    remote = git(repo, "config", "--get", f"branch.{branch}.remote")
    destination = git(repo, "config", "--get", f"branch.{branch}.merge")
    if not remote or remote == "." or not destination.startswith("refs/heads/"):
        raise RuntimeError(f"Configure a remote tracking branch before publishing: {repo}")
    return remote, f"HEAD:{destination}"


def refresh_resources(repo):
    """Use a dedicated clean checkout; CNB may replace history on each sync."""
    if not (repo / ".git").exists():
        if repo.exists() and any(repo.iterdir()):
            raise RuntimeError(f"Resource cache is not an empty Git checkout: {repo}")
        subprocess.run([
            "git", "clone", "--depth=1", "--filter=blob:none", "--sparse",
            SOURCE_REPOSITORY + ".git", str(repo),
        ], check=True)
    require_clean(repo)
    if git(repo, "remote", "get-url", "origin").rstrip("/") not in (
        SOURCE_REPOSITORY, SOURCE_REPOSITORY + ".git"
    ):
        raise RuntimeError(f"Unexpected origin in resource cache: {repo}")
    git(repo, "fetch", "--depth=1", "origin", "main")
    git(repo, "sparse-checkout", "set", "--no-cone", "--stdin", input_text=SPARSE_PATTERNS)
    git(repo, "checkout", "--detach", "FETCH_HEAD")


def _weights(value, label, positive=False):
    if not isinstance(value, (list, dict)):
        raise ValueError(f"Invalid weights: {label}")
    numbers = value.values() if isinstance(value, dict) else value
    for number in numbers:
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not math.isfinite(number) or number < 0 or (positive and number == 0)):
            raise ValueError(f"Invalid weight {number!r}: {label}")


def validate_template(template, path):
    if not isinstance(template, dict) or not isinstance(template.get("name"), str) or not template["name"]:
        raise ValueError(f"Missing template name: {path}")
    for cost in ("1", "3", "4"):
        _weights(template["main_props"][cost], f"{path}: main_props/{cost}")
    _weights(template["sub_props"], f"{path}: sub_props")
    if len(template["skill_weight"]) != 4 or len(template["score_max"]) != 3:
        raise ValueError(f"Unsupported scoring schema: {path}")
    _weights(template["skill_weight"], f"{path}: skill_weight")
    _weights(template["score_max"], f"{path}: score_max", positive=True)


def read_resources(repo):
    """Read exactly the tracked files, including additions and removals."""
    commit = git(repo, "rev-parse", "HEAD")
    paths = git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", RESOURCE_PATH).splitlines()
    templates, conditions = {}, {}
    for relative in paths:
        path = Path(relative)
        if path.name != "condition.json" and not re.fullmatch(r"calc(?:-[\w-]+)?\.json", path.name):
            continue
        character = path.parent.name
        payload = json.loads((repo / path).read_text(encoding="utf-8-sig"))
        if path.name == "condition.json":
            if not isinstance(payload, list):
                raise ValueError(f"Invalid modal conditions: {relative}")
            conditions[character] = payload
        else:
            validate_template(payload, relative)
            variant = "default" if path.stem == "calc" else path.stem.removeprefix("calc-")
            templates.setdefault(character, {})[variant] = payload
    if "default" not in templates.get("default", {}):
        raise ValueError("Missing generic default template; refusing incomplete snapshot")
    for character, variants in templates.items():
        if "default" not in variants:
            raise ValueError(f"Missing default calc.json for {character}")
    return commit, {"templates": templates, "conditions": conditions}


def differences(previous, current):
    def flatten(data):
        return {(char, mode): template for char, variants in data["templates"].items()
                for mode, template in variants.items()}
    old, new = flatten(previous), flatten(current)
    return {
        "added": [new[key]["name"] for key in sorted(new.keys() - old.keys())],
        "updated": [new[key]["name"] for key in sorted(new.keys() & old.keys()) if new[key] != old[key]],
        "removed": [old[key]["name"] for key in sorted(old.keys() - new.keys())],
        "conditions_changed": previous["conditions"] != current["conditions"],
    }


def snapshot_bytes(commit, data):
    encoded = base64.b85encode(zlib.compress(json.dumps(
        data, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8"), level=9)).decode("ascii")
    return (
        '"""Complete snapshot of XW-UID character/modal Echo score templates.\n\n'
        f'Source: {SOURCE_REPOSITORY}\nCommit: {commit}\n'
        f'Path: {RESOURCE_PATH}/<character>/calc*.json and condition.json\n'
        'Generated by scripts/update_xwuid_echo_templates.py.\n"""\n\n'
        'from __future__ import annotations\n\nimport base64\nimport json\nimport zlib\n\n'
        f'SOURCE_REPOSITORY = "{SOURCE_REPOSITORY}"\nSOURCE_COMMIT = "{commit}"\n'
        f'_ENCODED = r"""{encoded}"""\n\n'
        '_DATA = json.loads(zlib.decompress(base64.b85decode(_ENCODED)).decode("utf-8"))\n'
        'TEMPLATES = _DATA["templates"]\nCONDITIONS = _DATA["conditions"]\n'
    ).encode("utf-8")


def write_if_changed(path, content):
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temp.write(content)
        temporary = Path(temp.name)
    temporary.replace(path)
    return True


def next_version(current):
    if not re.fullmatch(r"\d+\.\d+\.\d+", current):
        raise ValueError(f"Expected major.minor.patch version: {current}")
    major, minor, patch = map(int, current.split("."))
    return f"{major}.{minor}.{patch + 1}"


def sync_and_zip(source, targets, names, zip_path):
    """Copy only build-managed files, keeping user files outside that set."""
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            content = (source / name).read_bytes()
            write_if_changed(target / name, content)
            if hashlib.sha256(content).digest() != hashlib.sha256((target / name).read_bytes()).digest():
                raise RuntimeError(f"Sync mismatch: {target / name}")
        print(f"Verified {len(names)} files: {target}")
    with tempfile.TemporaryDirectory(prefix="echo-score-zip-") as temp:
        temporary = Path(temp) / "echo-score.zip"
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(names):
                entry = zipfile.ZipInfo(f"echo-score/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, (source / name).read_bytes())
        with zipfile.ZipFile(temporary) as archive:
            if set(archive.namelist()) != {f"echo-score/{name}" for name in names}:
                raise RuntimeError("Unexpected archive entries")
            for name in names:
                if archive.read(f"echo-score/{name}") != (source / name).read_bytes():
                    raise RuntimeError(f"Archive mismatch: {name}")
        write_if_changed(zip_path, temporary.read_bytes())
    print(f"Verified ZIP: {zip_path}")


def publish(args, template_count):
    current = json.loads((ROOT / "echo-score" / "manifest.json").read_text(encoding="utf-8"))["version"]
    version = args.version or next_version(current)
    next_version(version)
    if tuple(map(int, version.split("."))) <= tuple(map(int, current.split("."))):
        raise ValueError(f"Release version {version} must be newer than {current}")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "Test*.py"], cwd=ROOT, check=True)
    sys.path.insert(0, str(ROOT))
    from scripts.build_echo_score_okscript import build, build_import_folder, IMPORT_FILES

    print(build(version=version))
    source = build_import_folder(version=version)
    sync_and_zip(source, [ROOT / "echo-score", args.install_dir, args.distribution / "echo-score"],
                 IMPORT_FILES, args.distribution / "echo-score.zip")
    readme = args.distribution / "README.md"
    text = readme.read_text(encoding="utf-8")
    text, replaced = re.subn(r"^当前脚本版本为.*$",
        f"当前脚本版本为 **{version}**，内置 {template_count} 套 XW-UID 角色/多模态评分模板。更新后请重启 OKWW，使新的脚本和模板列表加载生效。",
        text, flags=re.MULTILINE)
    if replaced != 1:
        raise ValueError("Expected one version paragraph in distribution README")
    write_if_changed(readme, text.encode("utf-8"))
    for repo in (ROOT, args.distribution):
        git(repo, "-c", "core.whitespace=cr-at-eol", "diff", "--check")
    if args.commit_push:
        message = f"chore: sync XW-UID echo templates ({version})"
        for repo, paths in (
            (ROOT, ["src/xwuid_echo_data.py", "echo-score"]),
            (args.distribution, ["echo-score", "echo-score.zip", "README.md"]),
        ):
            git(repo, "add", "--", *paths)
            git(repo, "commit", "-m", message)
        failures = []
        for repo in (ROOT, args.distribution):
            result = subprocess.run(["git", "-C", str(repo), "push", *push_target(repo)])
            if result.returncode:
                failures.append(str(repo))
        if failures:
            raise RuntimeError(f"Commits are saved locally; retry git push in: {', '.join(failures)}")
    print(f"Published local package {version}; restart OKWW to load it.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource_root", nargs="?", type=Path, default=ROOT.parent / "xwuid-score-resources")
    parser.add_argument("--check", action="store_true", help="fetch and compare, without writing project files")
    parser.add_argument("--no-fetch", action="store_true", help="use an already complete local resources checkout")
    parser.add_argument("--publish", action="store_true", help="test, build, sync all folders and regenerate ZIP")
    parser.add_argument("--commit-push", action="store_true", help="also commit and push both clean repositories")
    parser.add_argument("--force-package", action="store_true", help="rebuild even when templates are unchanged")
    parser.add_argument("--version", help="release version; defaults to incrementing the patch number")
    parser.add_argument("--distribution", type=Path, default=ROOT.parent / "okww-xwuid-echo-score")
    parser.add_argument("--install-dir", type=Path, default=Path("D:/ok-ww/data/apps/ok-ww/working/ok_import/echo-score"))
    args = parser.parse_args(argv)
    if args.check and (args.publish or args.commit_push or args.force_package):
        parser.error("--check cannot be combined with release options")
    args.publish = args.publish or args.commit_push or args.force_package
    if args.publish:
        if not (args.distribution / ".git").exists():
            raise RuntimeError(f"Distribution repository not found: {args.distribution}")
    if args.commit_push:
        require_clean(ROOT)
        require_clean(args.distribution)
        push_target(ROOT)
        push_target(args.distribution)
    if not args.no_fetch:
        refresh_resources(args.resource_root.resolve())
    else:
        require_clean(args.resource_root)
    commit, data = read_resources(args.resource_root.resolve())
    previous = runpy.run_path(str(SNAPSHOT))
    changes = differences({"templates": previous["TEMPLATES"], "conditions": previous["CONDITIONS"]}, data)
    count = sum(len(variants) for variants in data["templates"].values())
    print(f"XW-UID resources: {commit}; {count} templates")
    print(json.dumps(changes, ensure_ascii=False, indent=2))
    content = snapshot_bytes(commit, data)
    weights_changed = any(changes.values())
    # Resource commits also contain images and unrelated data. Only record a
    # new commit when scoring data changes (or when explicitly repackaging).
    changed = SNAPSHOT.read_bytes() != content and (
        weights_changed or "SOURCE_REPOSITORY" not in previous or args.force_package
    )
    if args.check:
        return 0
    if changed:
        write_if_changed(SNAPSHOT, content)
    print("Snapshot updated." if changed else "Snapshot already current.")
    if args.publish and (changed or args.force_package):
        publish(args, count)
    elif args.publish:
        print("No changes; skipping package, commits and pushes.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Update failed: {error}", file=sys.stderr)
        raise SystemExit(1)
