#!/usr/bin/env python3
"""
search-yaml.py — Generic YAML-frontmatter search tool for markdown document directories.

Works on any directory of .md files that use YAML frontmatter (--- ... ---).
Designed for AI agent use: fast, structured output, no required external dependencies.

Filter syntax (--filter flag, repeatable, AND logic):
  key=value     Exact match on a scalar field (case-insensitive)
  key=a|b       Exact match against any candidate value (OR)
  key~=value    Substring match on a string field, or element-in for list fields
  key~=a|b      Substring/list match against any candidate value (OR)

Usage examples:
  # Search .codestable/compound (learning / trick / decision / explore docs share this dir)
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --filter track=pitfall
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter "doc_type=decision|explore|learning"
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter tags~=prisma
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter status=active --full

  # Full-text search in body + frontmatter values
  python .codestable/tools/search-yaml.py --dir .codestable/compound --query "shadow database"

  # JSON output for AI agent consumption
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --filter track=knowledge --json

  # Sort by a frontmatter date field (works on any ISO-8601 date string, YAML date, or sortable value)
  python .codestable/tools/search-yaml.py --dir .codestable/library-docs --sort-by last_reviewed --order asc   # oldest first (stalest)
  python .codestable/tools/search-yaml.py --dir .codestable/compound --sort-by date --order desc              # newest first

  # Works on any yaml-frontmatter markdown directory
  python .codestable/tools/search-yaml.py --dir docs/decisions --filter status=accepted
  python .codestable/tools/search-yaml.py --dir content/posts --filter tags~=python --query "asyncio"
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
    _HAS_PYYAML = True
except ImportError:
    _HAS_PYYAML = False


# ---------------------------------------------------------------------------
# Frontmatter parsing  (PyYAML used when available, builtin fallback otherwise)
# ---------------------------------------------------------------------------

def _parse_yaml_scalar(val: str):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1]
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    lower = val.lower()
    if lower in ("true", "yes"):
        return True
    if lower in ("false", "no"):
        return False
    if lower in ("null", "~", ""):
        return None
    return val


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Split a markdown document into (frontmatter_dict, body_text).
    Returns ({}, full_text) when no frontmatter is present.
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 4:].strip()

    if _HAS_PYYAML:
        try:
            meta = yaml.safe_load(fm_text)
            return (meta or {}), body
        except yaml.YAMLError:
            # Malformed frontmatter — fall through to the lenient builtin parser
            # so partial / hand-written frontmatter still produces best-effort results.
            pass

    # Minimal fallback: handles scalar values and inline lists
    meta: dict = {}
    for line in fm_text.splitlines():
        if not line.strip() or line.startswith("#") or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        meta[key.strip()] = _parse_yaml_scalar(raw)

    return meta, body


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_documents(directory: Path) -> list[dict]:
    docs = []
    for md_file in sorted(directory.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[warn] Cannot read {md_file.name}: {exc}", file=sys.stderr)
            continue
        meta, body = parse_frontmatter(text)
        docs.append({
            "file": str(md_file.relative_to(directory)),
            "path": str(md_file),
            "meta": meta,
            "body": body,
        })
    return docs


# ---------------------------------------------------------------------------
# Filter parsing and evaluation
# ---------------------------------------------------------------------------

def _split_filter_values(value: str) -> list[str]:
    values = [part.strip() for part in value.split("|")]
    return [part for part in values if part] or [value.strip()]


class Filter:
    """Parsed representation of a single --filter expression."""

    def __init__(self, raw: str):
        if "~=" in raw:
            key, _, value = raw.partition("~=")
            self.key = key.strip()
            self.value = value.strip()
            self.values = _split_filter_values(self.value)
            self.operator = "contains"
        elif "=" in raw:
            key, _, value = raw.partition("=")
            self.key = key.strip()
            self.value = value.strip()
            self.values = _split_filter_values(self.value)
            self.operator = "exact"
        else:
            raise argparse.ArgumentTypeError(
                f"Invalid filter expression {raw!r}. "
                "Use 'key=value' for exact match or 'key~=value' for substring/list-contains match. "
                "Use pipes for OR values, e.g. 'doc_type=decision|explore|learning'."
            )

    def matches(self, meta: dict) -> bool:
        field_val = meta.get(self.key)
        if field_val is None:
            return False

        if self.operator == "exact":
            return any(str(field_val).lower() == value.lower() for value in self.values)

        # contains: substring for strings, element-in for lists
        if isinstance(field_val, list):
            return any(
                value.lower() == str(item).lower()
                for value in self.values
                for item in field_val
            )
        return any(value.lower() in str(field_val).lower() for value in self.values)

    def __repr__(self):
        op = "~=" if self.operator == "contains" else "="
        return f"Filter({self.key}{op}{self.value})"


def parse_filter(raw: str) -> Filter:
    """argparse type converter for --filter."""
    return Filter(raw)


_MISSING = object()


def _sort_key(doc: dict, field: str):
    """
    Sort key for --sort-by. Docs missing the field sort to the end regardless
    of --order. Dates (datetime.date / datetime.datetime) and strings are both
    normalized to their string form — ISO 8601 date strings sort the same
    lexicographically as YAML-parsed date objects' isoformat().
    """
    val = doc["meta"].get(field, _MISSING)
    if val is _MISSING or val is None:
        return (1, "")
    try:
        return (0, val.isoformat())  # datetime.date / datetime.datetime
    except AttributeError:
        return (0, str(val))


def doc_matches(doc: dict, filters: list[Filter], query: str | None) -> bool:
    meta = doc["meta"]

    for f in filters:
        if not f.matches(meta):
            return False

    if query:
        needle = query.lower()
        haystack = doc["body"].lower() + " " + " ".join(str(v) for v in meta.values()).lower()
        if needle not in haystack:
            return False

    return True


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _meta_summary(meta: dict) -> str:
    """One-line summary of frontmatter fields, skipping slug/date for brevity."""
    skip = {"slug"}
    parts = []
    for k, v in meta.items():
        if k in skip:
            continue
        if isinstance(v, list):
            parts.append(f"{k}=[{', '.join(str(i) for i in v)}]")
        else:
            parts.append(f"{k}={v}")
    return "  ".join(parts)


def format_summary(doc: dict) -> str:
    return f"### {doc['file']}\n{_meta_summary(doc['meta'])}"


def format_full(doc: dict) -> str:
    return format_summary(doc) + "\n\n" + doc["body"]


def print_text(results: list[dict], full: bool) -> None:
    print(f"Found {len(results)} document(s).\n")
    sep = "\n" + "─" * 60 + "\n"
    chunks = [format_full(d) if full else format_summary(d) for d in results]
    print(sep.join(chunks))


def print_json(results: list[dict], full: bool) -> None:
    output = []
    for doc in results:
        body = doc["body"]
        if not full and len(body) > 400:
            body = body[:400] + "…"
        output.append({"file": doc["file"], "meta": doc["meta"], "body": body})
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generic YAML-frontmatter search across a directory of markdown files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dir", metavar="DIR", required=True,
                        help="Directory of .md files to search.")
    parser.add_argument("--filter", "-f", metavar="EXPR", dest="filters",
                        type=parse_filter, action="append", default=[],
                        help="Frontmatter filter expression. Repeatable (AND logic). "
                             "key=value for exact match; key~=value for substring (strings) or element-in (lists). "
                             "Use pipes for OR values, e.g. key=a|b.")
    parser.add_argument("--query", "-q", metavar="TEXT",
                        help="Full-text search in document body and frontmatter values.")
    parser.add_argument("--full", action="store_true",
                        help="Print full document body instead of just the frontmatter summary.")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Output results as a JSON array.")
    parser.add_argument("--sort-by", metavar="FIELD", dest="sort_by",
                        help="Sort results by a frontmatter field (e.g. last_reviewed, date, updated_at). "
                             "ISO-8601 date strings and YAML-parsed dates both sort correctly. "
                             "Docs missing the field are pushed to the end.")
    parser.add_argument("--order", choices=("asc", "desc"), default="desc",
                        help="Sort order when --sort-by is set. Default: desc (newest first).")
    return parser


def _resolve_directory(dir_arg: str) -> Path:
    directory = Path(dir_arg)
    if not directory.exists():
        print(f"[error] Directory not found: {directory}", file=sys.stderr)
        sys.exit(1)
    if not directory.is_dir():
        print(f"[error] Not a directory: {directory}", file=sys.stderr)
        sys.exit(1)
    return directory


def _sort_results(results: list[dict], sort_by: str, order: str) -> list[dict]:
    def has_field(d: dict) -> bool:
        return sort_by in d["meta"] and d["meta"][sort_by] is not None

    present = [d for d in results if has_field(d)]
    missing = [d for d in results if not has_field(d)]
    present.sort(key=lambda d: _sort_key(d, sort_by), reverse=(order == "desc"))
    return present + missing


def main() -> None:
    args = _build_parser().parse_args()
    directory = _resolve_directory(args.dir)

    docs = load_documents(directory)
    if not docs:
        print(f"No .md files found in {directory}")
        return

    results = [d for d in docs if doc_matches(d, args.filters, args.query)]
    if not results:
        print("No matching documents found.")
        return

    if args.sort_by:
        results = _sort_results(results, args.sort_by, args.order)

    if args.as_json:
        print_json(results, full=args.full)
    else:
        print_text(results, full=args.full)


if __name__ == "__main__":
    main()
