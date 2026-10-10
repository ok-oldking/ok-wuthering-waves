#!/usr/bin/env python3
"""Pinned PR snapshots, problem comments with PR closure, and squash merges.

Review judgment belongs to the agent; this helper handles Git and API mechanics.
Uses standard-library Python, Git, and existing GitHub credentials. No shell=True.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


class ToolError(RuntimeError):
    pass


def run(argv, cwd, *, stdin=None, env=None):
    result = subprocess.run(argv, cwd=cwd, input=stdin, text=True,
                            encoding="utf-8", errors="replace", capture_output=True,
                            env=env)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ToolError(f"{argv[0]} {argv[1]} failed: {detail}")
    return result.stdout.strip()


class Repository:
    def __init__(self, cwd, remote="origin"):
        self.root = Path(run(["git", "rev-parse", "--show-toplevel"], cwd)).resolve()
        self.remote = remote
        if remote.startswith("-"):
            raise ToolError("Remote must be a configured remote name.")
        url = self.git("remote", "get-url", remote)
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                             r"([\w.-]+/[\w.-]+?)(?:\.git)?/?", url)
        if not match:
            raise ToolError("Selected remote must point to a github.com repository.")
        self.name = match.group(1)
        push_url = self.git("remote", "get-url", "--push", remote)
        if push_url != url:
            raise ToolError("Fetch and push URLs differ; select a consistent remote.")

    def git(self, *args, cwd=None):
        return run(["git", *args], cwd or self.root)

    def fetch_base(self, branch):
        self.git("check-ref-format", f"refs/heads/{branch}")
        ref = f"refs/remotes/{self.remote}/{branch}"
        self.git("fetch", "--no-tags", self.remote,
                 f"+refs/heads/{branch}:{ref}")
        return self.git("rev-parse", ref)

    def fetch_head(self, number, expected):
        self.git("fetch", "--no-tags", self.remote, f"refs/pull/{number}/head")
        actual = self.git("rev-parse", "FETCH_HEAD")
        if actual != expected:
            raise ToolError("PR changed during fetch; collect a fresh snapshot.")
        return actual


class GitHub:
    def __init__(self, repo):
        self.repo = repo
        self._token = None
        self._loaded = False
        self._public_reads = False

    def token(self):
        if not self._loaded:
            self._loaded = True
            self._token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            if not self._token:
                env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
                result = subprocess.run(
                    ["git", "credential", "fill"], cwd=self.repo.root,
                    input="protocol=https\nhost=github.com\n\n", text=True,
                    capture_output=True, env=env, timeout=30)
                if not result.returncode:
                    fields = dict(line.split("=", 1) for line in result.stdout.splitlines()
                                  if "=" in line)
                    self._token = fields.get("password")
        return self._token

    def request(self, path, method="GET", data=None):
        token = self.token()
        if method != "GET" and not token:
            raise ToolError("GitHub write needs GH_TOKEN, GITHUB_TOKEN, or a Git credential.")
        headers = {"Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ok-ww-pr-review"}
        if token and not (method == "GET" and self._public_reads and path != "user"):
            headers["Authorization"] = f"Bearer {token}"
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"https://api.github.com/{path}", headers=headers,
                          data=json.dumps(data).encode("utf-8") if data is not None else None,
                          method=method)
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            if (exc.code == 401 and method == "GET" and path != "user"
                    and "Authorization" in headers):
                self._public_reads = True
                print("Saved GitHub API credential rejected; trying public reads. "
                      "Comments and merges need a valid GH_TOKEN or refreshed Git credential.",
                      file=sys.stderr)
                return self.request(path)
            try:
                message = json.load(exc).get("message", "API request failed")
            except (ValueError, AttributeError):
                message = "API request failed"
            hint = " Set GH_TOKEN/GITHUB_TOKEN locally or refresh the Git credential." if exc.code == 401 else ""
            raise ToolError(f"GitHub {method} failed ({exc.code}): {message}.{hint}") from None
        except (URLError, TimeoutError) as exc:
            suffix = " Mutation outcome may be unknown; inspect GitHub before retrying." if method != "GET" else ""
            raise ToolError(f"GitHub network failure: {exc}.{suffix}") from None

    def api(self, suffix, method="GET", data=None):
        return self.request(f"repos/{self.repo.name}/{suffix}", method, data)

    def pages(self, suffix, *, key=None, params=None):
        items, page = [], 1
        while True:
            query = dict(params or {}, per_page=100, page=page)
            result = self.api(f"{suffix}?{urlencode(query)}")
            batch = result[key] if key else result
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def pr(self, number):
        return self.api(f"pulls/{number}")

    def checks(self, head):
        return {
            "status": self.api(f"commits/{head}/status"),
            "runs": self.pages(f"commits/{head}/check-runs", key="check_runs",
                               params={"filter": "latest"}),
        }


def assert_current(pr, head, base=None, *, allow_closed=False):
    if (pr["state"] != "open" and not (allow_closed and pr["state"] == "closed")) or pr.get("merged"):
        raise ToolError("PR is no longer open.")
    if pr["head"]["sha"] != head:
        raise ToolError("PR head changed; review a fresh snapshot.")
    if base is not None and pr["base"]["sha"] != base:
        raise ToolError("PR base changed; review a fresh snapshot.")


def blockers(pr, checks, reviews):
    problems = []
    if pr["state"] != "open" or pr.get("merged"):
        problems.append("PR is not open")
    if pr.get("draft"):
        problems.append("PR is a draft")
    if pr["base"]["ref"] != "master":
        problems.append("PR does not target master")
    if pr.get("mergeable") is not True:
        problems.append("GitHub mergeability is conflicting or not yet known")
    if pr.get("mergeable_state") in {"blocked", "dirty", "behind", "draft", "unstable"}:
        problems.append(f"GitHub merge state: {pr['mergeable_state']}")
    status = checks["status"]
    if status.get("total_count", 0) and status["state"] != "success":
        problems.append(f"Commit status is {status['state']}")
    for check in checks["runs"]:
        if check["status"] != "completed" or check.get("conclusion") not in {"success", "neutral", "skipped"}:
            problems.append(f"Check {check['name']}: {check['status']}/{check.get('conclusion')}")
    latest = {}
    for review in sorted(reviews, key=lambda r: r["id"]):
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[review["user"]["login"]] = review["state"]
    for author, state in latest.items():
        if state == "CHANGES_REQUESTED":
            problems.append(f"Active change request by {author}")
    return problems


def save(directory, record):
    target = Path(directory) / "snapshot.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(target)


def load(directory, repo):
    directory = Path(directory).resolve()
    record = json.loads((directory / "snapshot.json").read_text(encoding="utf-8"))
    if record["repository"] != repo.name or Path(record["repository_root"]).resolve() != repo.root:
        raise ToolError("Snapshot belongs to a different repository checkout.")
    checkout = Path(record["checkout"]).resolve()
    if checkout != directory / "checkout":
        raise ToolError("Snapshot checkout is not inside its snapshot directory.")
    for key in ("head", "base"):
        if not re.fullmatch(r"[0-9a-f]{40,64}", record[key]):
            raise ToolError("Invalid snapshot commit.")
    return directory, record, checkout


def collect(repo, api, number, output=None, prepare=False):
    pr = api.pr(number)
    if pr["state"] != "open":
        raise ToolError("Snapshot requires an open PR.")
    head = repo.fetch_head(number, pr["head"]["sha"])
    base = repo.fetch_base(pr["base"]["ref"])
    pr = api.pr(number)
    assert_current(pr, head, base)
    checks = api.checks(head)
    reviews = api.pages(f"pulls/{number}/reviews")
    if prepare:
        problems = blockers(pr, checks, reviews)
        if problems:
            raise ToolError("Merge blocked: " + "; ".join(problems))
    if output:
        directory = Path(output).resolve()
        directory.mkdir(parents=True, exist_ok=False)
    else:
        directory = Path(tempfile.mkdtemp(prefix=f"ok-ww-pr-{number}-")).resolve()
    checkout = directory / "checkout"
    record = {
        "repository": repo.name, "repository_root": str(repo.root), "number": number,
        "head": head, "base": base, "checkout": str(checkout),
        "mode": "merge" if prepare else "review", "pr": pr, "checks": checks,
        "reviews": reviews, "comments": api.pages(f"issues/{number}/comments"),
        "inline_comments": api.pages(f"pulls/{number}/comments"),
        "files": api.pages(f"pulls/{number}/files"),
    }
    # Disable hooks while creating worktrees from untrusted PR contents.
    repo.git("-c", "core.hooksPath=", "worktree", "add", "--detach", str(checkout),
             base if prepare else head)
    save(directory, record)  # Retain enough information for cleanup if squash conflicts.
    diff = repo.git("diff", "--no-ext-diff", "--no-textconv", f"{base}...{head}")
    (directory / "diff.patch").write_text(diff + "\n", encoding="utf-8")
    if prepare:
        try:
            repo.git("-c", "core.hooksPath=", "merge", "--squash", "--no-commit", head, cwd=checkout)
        except ToolError as exc:
            raise ToolError(f"{exc}\nSnapshot retained at {directory}") from None
        if not repo.git("diff", "--cached", "--name-only", cwd=checkout):
            raise ToolError(f"PR has no changes to merge. Snapshot retained at {directory}")
        record["preview_tree"] = repo.git("write-tree", cwd=checkout)
        save(directory, record)
    return {"number": number, "head": head, "base": base, "snapshot": str(directory),
            "checkout": str(checkout), "mode": record["mode"]}


def comment(repo, api, number, directory, body_file, model):
    model = model.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._:/()+-]{0,127}", model):
        raise ToolError("Provide the current reviewer model's name as a single plain-text name.")
    directory, record, _ = load(directory, repo)
    if record["number"] != number:
        raise ToolError("PR number does not match snapshot.")
    pr = api.pr(number)
    assert_current(pr, record["head"], record["base"], allow_closed=True)
    body = Path(body_file).read_text(encoding="utf-8-sig").strip()
    if not body:
        raise ToolError("Comment body is empty.")
    body = (f"{body}\n\nReviewed by {model}.\n\n"
            "Please reopen this PR after fixing the problems, or if you have a different opinion about this review.")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]
    marker = f"<!-- ok-ww-pr-review:{record['head']}:{digest} -->"
    me = api.request("user")
    posted = None
    for previous in api.pages(f"issues/{number}/comments"):
        if previous["user"]["id"] == me["id"] and marker in previous["body"]:
            posted = previous
            break
    duplicate = posted is not None
    if pr["state"] == "closed":
        if duplicate:
            return {"comment": posted["html_url"], "duplicate_skipped": True, "pr_closed": True}
        raise ToolError("PR was closed independently; no new comment or closure performed.")
    previous_result = record.get("problem_review_result", {})
    if previous_result.get("pr_closed"):
        raise ToolError("PR was reopened after this review; collect a fresh snapshot and consider the author's response.")
    # Recheck after paginating comments; do not post an already-stale review.
    assert_current(api.pr(number), record["head"], record["base"])
    if not posted:
        posted = api.api(f"issues/{number}/comments", "POST", {
            "body": f"{body}\n\nReviewed head `{record['head']}`, base `{record['base']}`.\n\n{marker}"})
    result = {"comment": posted["html_url"], "duplicate_skipped": duplicate, "pr_closed": False}
    try:
        # Posting and closing are separate API mutations. Never close a newly changed PR.
        assert_current(api.pr(number), record["head"], record["base"])
        closed = api.api(f"pulls/{number}", "PATCH", {"state": "closed"})
        result["pr_closed"] = closed.get("state") == "closed" and not closed.get("merged")
        if not result["pr_closed"]:
            raise ToolError("GitHub did not confirm PR closure; inspect its current state.")
        assert_current(closed, record["head"], record["base"], allow_closed=True)
    except ToolError as exc:
        result["close_error"] = str(exc)
    record["problem_review_result"] = dict(result, marker=marker, model=model)
    save(directory, record)
    return result


def master_plan(repo, base):
    """Verify local master can be advanced without losing existing work."""
    refs = repo.git("for-each-ref", "--format=%(objectname)", "refs/heads/master")
    old = refs.strip() or None
    if old:
        try:
            repo.git("merge-base", "--is-ancestor", old, base)
        except ToolError:
            raise ToolError("Local master contains unpublished or diverged commits; synchronize it before merging.") from None
    checkout = None
    for section in repo.git("worktree", "list", "--porcelain", "-z").split("\0\0"):
        fields = dict(line.split(" ", 1) for line in section.split("\0") if " " in line)
        if fields.get("branch") == "refs/heads/master":
            checkout = Path(fields["worktree"])
            if repo.git("status", "--porcelain", "--untracked-files=no", cwd=checkout):
                raise ToolError(f"Local master checkout has changes: {checkout}")
    return old, checkout


def sync_master(repo, expected_base):
    tip = repo.fetch_base("master")
    repo.git("merge-base", "--is-ancestor", expected_base, tip)
    old, checkout = master_plan(repo, tip)
    if checkout:
        repo.git("-c", "core.hooksPath=", "merge", "--ff-only", tip, cwd=checkout)
    else:
        repo.git("update-ref", "refs/heads/master", tip, old or "0" * 40)
    return tip


def merge(repo, api, number, directory, verification):
    directory, record, checkout = load(directory, repo)
    if record["number"] != number or record["mode"] != "merge":
        raise ToolError("Use a prepare-merge snapshot for this PR.")
    if record.get("merge_result") or record.get("merge_attempted"):
        raise ToolError("Merge already attempted; inspect GitHub and snapshot before any retry.")
    if not verification.strip():
        raise ToolError("Provide verification commands, results, and material limits.")
    if repo.git("rev-parse", "HEAD", cwd=checkout) != record["base"]:
        raise ToolError("Preview checkout commit changed.")
    if repo.git("diff", "--name-only", cwd=checkout):
        raise ToolError("Preview has unstaged changes; review them before merging.")
    if repo.git("write-tree", cwd=checkout) != record.get("preview_tree"):
        raise ToolError("Preview staged tree changed; prepare and verify again.")
    pr = api.pr(number)
    assert_current(pr, record["head"], record["base"])
    problems = blockers(pr, api.checks(record["head"]), api.pages(f"pulls/{number}/reviews"))
    if problems:
        raise ToolError("Merge blocked: " + "; ".join(problems))
    if repo.fetch_base("master") != record["base"]:
        raise ToolError("Remote master advanced; prepare and verify a new preview.")
    master_plan(repo, record["base"])
    assert_current(api.pr(number), record["head"], record["base"])
    record["verification"] = verification
    record["merge_attempted"] = True
    save(directory, record)
    result = api.api(f"pulls/{number}/merge", "PUT", {
        "sha": record["head"], "merge_method": "squash",
        "commit_title": f"{pr['title']} (#{number})",
    })
    record["merge_result"] = result
    save(directory, record)
    if not result.get("merged"):
        raise ToolError("GitHub did not merge: " + result.get("message", "unknown reason"))
    # Persist the remote result before syncing, so a failed fetch cannot hide publication.
    output = {"pr": pr["html_url"], "merged": True, "commit": result["sha"],
              "verification": verification, "local_master_synced": False}
    try:
        tip = sync_master(repo, record["base"])
        output["local_master_synced"] = True
        output["local_master"] = tip
        actual_tree = repo.git("rev-parse", f"{result['sha']}^{{tree}}")
        output["preview_matches_merge"] = actual_tree == record["preview_tree"]
        if not output["preview_matches_merge"]:
            output["warning"] = "Published merge differs from preview; master may have advanced during API merge. Inspect the published diff."
    except ToolError as exc:
        output["sync_error"] = str(exc)
    record["completion"] = output
    save(directory, record)
    return output


def resume_sync(repo, api, directory):
    """Recover synchronization after an uncertain or successful API mutation."""
    directory, record, _ = load(directory, repo)
    if record["mode"] != "merge" or not record.get("merge_attempted"):
        raise ToolError("Snapshot has no merge attempt to synchronize.")
    pr = api.pr(record["number"])
    if not pr.get("merged") or pr["head"]["sha"] != record["head"]:
        raise ToolError("GitHub has not merged the reviewed PR head; no local sync performed.")
    commit = pr["merge_commit_sha"]
    record["merge_result"] = {"merged": True, "sha": commit, "message": "Confirmed on GitHub"}
    save(directory, record)
    tip = sync_master(repo, record["base"])
    repo.git("merge-base", "--is-ancestor", commit, tip)
    output = {"pr": pr["html_url"], "merged": True, "commit": commit,
              "local_master_synced": True, "local_master": tip,
              "preview_matches_merge": repo.git("rev-parse", f"{commit}^{{tree}}") == record["preview_tree"]}
    record["completion"] = output
    save(directory, record)
    return output


def cleanup(repo, directory):
    directory, record, checkout = load(directory, repo)
    if checkout.exists():
        if repo.git("diff", "--name-only", cwd=checkout):
            raise ToolError("Retaining checkout with unstaged changes.")
        if repo.git("ls-files", "--others", cwd=checkout):
            raise ToolError("Retaining checkout with untracked files.")
        staged = repo.git("diff", "--cached", "--name-only", cwd=checkout)
        if staged and (record["mode"] != "merge" or
                       repo.git("write-tree", cwd=checkout) != record.get("preview_tree")):
            raise ToolError("Retaining checkout with unexpected staged changes.")
        args = ["worktree", "remove"]
        if staged:
            args.append("--force")  # Only the exact helper-created squash preview.
        repo.git(*args, str(checkout))
    return {"checkout_removed": True, "snapshot_retained": str(directory)}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("PR number must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="origin")
    sub = parser.add_subparsers(dest="command", required=True)
    queue = sub.add_parser("list", help="All open PRs at or above an inclusive number")
    queue.add_argument("--start", type=positive, required=True)
    for command in ("inspect", "prepare-merge"):
        item = sub.add_parser(command)
        item.add_argument("number", type=positive)
        item.add_argument("--output", help="New snapshot directory (default: system temp)")
    post = sub.add_parser("comment", help="Post a problem review, then close the PR")
    post.add_argument("number", type=positive)
    post.add_argument("--snapshot", required=True)
    post.add_argument("--body-file", required=True)
    post.add_argument("--model", required=True, help="Name of the model that performed this review")
    publish = sub.add_parser("merge", help="GitHub squash merge; then fast-forward local master")
    publish.add_argument("number", type=positive)
    publish.add_argument("--snapshot", required=True)
    publish.add_argument("--verification", required=True)
    clean = sub.add_parser("cleanup")
    clean.add_argument("--snapshot", required=True)
    sync = sub.add_parser("sync", help="Resume local synchronization without repeating the merge")
    sync.add_argument("--snapshot", required=True)
    args = parser.parse_args()
    repo = Repository(Path.cwd(), args.remote)
    api = GitHub(repo)
    if args.command == "list":
        prs = api.pages("pulls", params={"state": "open", "sort": "created", "direction": "asc"})
        result = [{"number": pr["number"], "title": pr["title"], "url": pr["html_url"],
                   "draft": pr["draft"], "base": pr["base"]["ref"], "head": pr["head"]["sha"]}
                  for pr in sorted(prs, key=lambda p: p["number"]) if pr["number"] >= args.start]
    elif args.command in {"inspect", "prepare-merge"}:
        result = collect(repo, api, args.number, args.output, args.command == "prepare-merge")
    elif args.command == "comment":
        result = comment(repo, api, args.number, args.snapshot, args.body_file, args.model)
    elif args.command == "merge":
        result = merge(repo, api, args.number, args.snapshot, args.verification)
    elif args.command == "sync":
        result = resume_sync(repo, api, args.snapshot)
    else:
        result = cleanup(repo, args.snapshot)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    incomplete = isinstance(result, dict) and (
        (result.get("merged") and (not result.get("local_master_synced") or
                                  result.get("preview_matches_merge") is False)) or
        ("pr_closed" in result and (not result["pr_closed"] or result.get("close_error"))))
    return 2 if incomplete else 0


if __name__ == "__main__":
    # PowerShell's default Python code page can corrupt Chinese PR titles.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        sys.exit(main())
    except (ToolError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
