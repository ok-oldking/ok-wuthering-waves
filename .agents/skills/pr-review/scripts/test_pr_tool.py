"""Offline behavior tests using real temporary Git repositories and a fake API."""

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import pr_tool as tool


class FakeAPI:
    def __init__(self, repo, head, base):
        self.repo = repo
        self.pull = {"number": 1752, "title": "Fix behavior", "body": "A test PR",
                     "html_url": "https://github.com/example/repo/pull/1752",
                     "state": "open", "draft": False, "merged": False,
                     "mergeable": True, "mergeable_state": "clean",
                     "head": {"sha": head}, "base": {"sha": base, "ref": "master"}}
        self.check_data = {"status": {"total_count": 0, "state": "pending"}, "runs": []}
        self.reviews = []
        self.comments = []
        self.writes = []
        self.preview_tree = None

    def pr(self, number):
        return copy.deepcopy(self.pull)

    def checks(self, head):
        return copy.deepcopy(self.check_data)

    def pages(self, suffix, **kwargs):
        if suffix.endswith("/reviews"):
            return copy.deepcopy(self.reviews)
        if suffix.startswith("issues/"):
            return copy.deepcopy(self.comments)
        return []

    def request(self, path):
        assert path == "user"
        return {"id": 1}

    def api(self, suffix, method="GET", data=None):
        self.writes.append((suffix, method, data))
        if method == "POST":
            posted = {"user": {"id": 1}, "body": data["body"],
                      "html_url": "https://github.com/example/repo/pull/1752#issuecomment-1"}
            self.comments.append(posted)
            return posted
        if method == "PATCH":
            assert suffix == "pulls/1752" and data == {"state": "closed"}
            self.pull["state"] = "closed"
            return copy.deepcopy(self.pull)
        assert method == "PUT" and data["merge_method"] == "squash"
        assert data["sha"] == self.pull["head"]["sha"]
        # Emulate GitHub's squash publication into the bare remote.
        commit = self.repo.git("commit-tree", self.preview_tree, "-p", self.pull["base"]["sha"],
                               "-m", data["commit_title"])
        self.repo.git("push", "origin", f"{commit}:refs/heads/master")
        self.pull.update(state="closed", merged=True, merge_commit_sha=commit)
        return {"merged": True, "sha": commit, "message": "Merged"}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pr-tool-test-")
        self.directory = Path(self.temp.name)
        bare = self.directory / "remote.git"
        work = self.directory / "repo"
        tool.run(["git", "init", "--bare", str(bare)], self.directory)
        tool.run(["git", "init", "-b", "master", str(work)], self.directory)
        tool.run(["git", "config", "user.name", "Test"], work)
        tool.run(["git", "config", "user.email", "test@example.invalid"], work)
        tool.run(["git", "config", "commit.gpgSign", "false"], work)
        tool.run(["git", "config", "core.autocrlf", "false"], work)
        (work / "behavior.txt").write_text("original\n", encoding="utf-8")
        tool.run(["git", "add", "behavior.txt"], work)
        tool.run(["git", "commit", "-m", "Initial"], work)
        base = tool.run(["git", "rev-parse", "HEAD"], work)
        tool.run(["git", "remote", "add", "origin", "https://github.com/example/repo.git"], work)
        # URL rewriting lets production repository validation run against a local remote.
        tool.run(["git", "config", f"url.{bare.as_posix()}.insteadOf",
                  "https://github.com/example/repo.git"], work)
        # get-url expands insteadOf; fake just the metadata lookup, retaining real Git I/O.
        original_run = tool.run

        def local_run(argv, cwd, **kwargs):
            if argv[:3] == ["git", "remote", "get-url"]:
                return "https://github.com/example/repo.git"
            return original_run(argv, cwd, **kwargs)

        self.run_patch = patch.object(tool, "run", side_effect=local_run)
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.repo = tool.Repository(work)
        self.repo.git("push", "origin", "master")
        (work / "behavior.txt").write_text("fixed\n", encoding="utf-8")
        self.repo.git("commit", "-am", "Fix")
        head = self.repo.git("rev-parse", "HEAD")
        self.repo.git("push", "origin", f"{head}:refs/pull/1752/head")
        self.repo.git("reset", "--hard", base)
        self.api = FakeAPI(self.repo, head, base)
        self.addCleanup(self.temp.cleanup)

    def snapshot(self, prepare=False):
        return tool.collect(self.repo, self.api, 1752,
                            self.directory / "snapshot", prepare=prepare)

    def prepare(self):
        result = self.snapshot(prepare=True)
        record = json.loads((Path(result["snapshot"]) / "snapshot.json").read_text())
        self.api.preview_tree = record["preview_tree"]
        return result

    def test_snapshot_pins_head_and_preserves_user_changes(self):
        (self.repo.root / "behavior.txt").write_text("user edits\n")
        result = self.snapshot()
        self.assertEqual((Path(result["checkout"]) / "behavior.txt").read_text(), "fixed\n")
        self.assertEqual((self.repo.root / "behavior.txt").read_text(), "user edits\n")
        self.assertIn("+fixed", (Path(result["snapshot"]) / "diff.patch").read_text())
        tool.cleanup(self.repo, result["snapshot"])
        self.assertFalse(Path(result["checkout"]).exists())

    def test_comment_is_deduplicated_and_rejects_changed_head(self):
        result = self.snapshot()
        body = self.directory / "comment.md"
        body.write_text("[P2] Reproducible problem with evidence.", encoding="utf-8")
        first = tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        second = tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        self.assertFalse(first["duplicate_skipped"])
        self.assertTrue(second["duplicate_skipped"])
        self.assertEqual([write[1] for write in self.api.writes], ["POST", "PATCH"])
        self.assertTrue(first["pr_closed"])
        self.assertTrue(second["pr_closed"])
        self.assertIn("Reviewed by gpt-6.1-sol.", self.api.comments[0]["body"])
        self.assertIn("Please reopen this PR after fixing the problems, or if you have a different opinion",
                      self.api.comments[0]["body"])
        self.api.pull["state"] = "open"  # An author can reopen for a new review by another model.
        fresh = tool.collect(self.repo, self.api, 1752, self.directory / "fresh-snapshot")
        other = tool.comment(self.repo, self.api, 1752, fresh["snapshot"], body, "gpt-6-astra")
        self.assertFalse(other["duplicate_skipped"])
        self.assertIn("Reviewed by gpt-6-astra.", self.api.comments[1]["body"])
        self.api.pull["head"]["sha"] = "a" * 40
        with self.assertRaisesRegex(tool.ToolError, "head changed"):
            tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")

    def test_comment_rejects_missing_or_multiline_model_without_posting(self):
        for model in ("", "  ", "gpt-6.1-sol\nReviewed by someone else"):
            with self.subTest(model=model):
                with self.assertRaisesRegex(tool.ToolError, "reviewer model's name"):
                    tool.comment(self.repo, self.api, 1752, self.directory / "unused",
                                 self.directory / "unused.md", model)
        self.assertFalse(self.api.writes)

    def test_comment_post_failure_does_not_close_pr(self):
        result = self.snapshot()
        body = self.directory / "comment.md"
        body.write_text("Verified problem", encoding="utf-8")
        with patch.object(self.api, "api", side_effect=tool.ToolError("Comment failed")) as write:
            with self.assertRaisesRegex(tool.ToolError, "Comment failed"):
                tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        self.assertEqual(write.call_count, 1)
        self.assertEqual(write.call_args.args[1], "POST")
        self.assertEqual(self.api.pull["state"], "open")

    def test_comment_close_failure_reports_link_and_retry_does_not_repost(self):
        result = self.snapshot()
        body = self.directory / "comment.md"
        body.write_text("Verified problem", encoding="utf-8")
        original = self.api.api

        def fail_close(suffix, method, data):
            if method == "PATCH":
                raise tool.ToolError("Close failed")
            return original(suffix, method, data)

        with patch.object(self.api, "api", side_effect=fail_close):
            output = tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        self.assertFalse(output["pr_closed"])
        self.assertEqual(output["close_error"], "Close failed")
        self.assertIn("issuecomment-1", output["comment"])
        retried = tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        self.assertTrue(retried["duplicate_skipped"])
        self.assertTrue(retried["pr_closed"])
        self.assertEqual([write[1] for write in self.api.writes], ["POST", "PATCH"])

    def test_comment_does_not_close_pr_changed_after_posting(self):
        result = self.snapshot()
        body = self.directory / "comment.md"
        body.write_text("Verified problem", encoding="utf-8")
        original = self.api.api

        def change_after_post(suffix, method, data):
            posted = original(suffix, method, data)
            self.api.pull["head"]["sha"] = "a" * 40
            return posted

        with patch.object(self.api, "api", side_effect=change_after_post):
            output = tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        self.assertFalse(output["pr_closed"])
        self.assertIn("head changed", output["close_error"])
        self.assertEqual(self.api.pull["state"], "open")
        self.assertEqual([write[1] for write in self.api.writes], ["POST"])

    def test_comment_does_not_reclose_reopened_pr_from_old_snapshot(self):
        result = self.snapshot()
        body = self.directory / "comment.md"
        body.write_text("Verified problem", encoding="utf-8")
        tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        self.api.pull["state"] = "open"
        with self.assertRaisesRegex(tool.ToolError, "reopened after this review"):
            tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6.1-sol")
        with self.assertRaisesRegex(tool.ToolError, "reopened after this review"):
            tool.comment(self.repo, self.api, 1752, result["snapshot"], body, "gpt-6-astra")
        self.assertEqual(self.api.pull["state"], "open")
        self.assertEqual([write[1] for write in self.api.writes], ["POST", "PATCH"])

    def test_successful_squash_merge_syncs_master_and_rejects_retry(self):
        result = self.prepare()
        output = tool.merge(self.repo, self.api, 1752, result["snapshot"], "Reviewed and tested")
        self.assertTrue(output["merged"])
        self.assertTrue(output["local_master_synced"])
        self.assertTrue(output["preview_matches_merge"])
        self.assertEqual(self.repo.git("rev-parse", "master"), output["commit"])
        self.assertEqual((self.repo.root / "behavior.txt").read_text(), "fixed\n")
        self.assertEqual(self.repo.git("rev-list", "--count", "master"), "2")
        with self.assertRaisesRegex(tool.ToolError, "already attempted"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Repeated")
        tool.cleanup(self.repo, result["snapshot"])

    def test_merge_keeps_current_branch_and_unrelated_changes(self):
        self.repo.git("switch", "-c", "user-work")
        (self.repo.root / "behavior.txt").write_text("user changes\n")
        result = self.prepare()
        output = tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertTrue(output["local_master_synced"])
        self.assertEqual(self.repo.git("branch", "--show-current"), "user-work")
        self.assertEqual((self.repo.root / "behavior.txt").read_text(), "user changes\n")
        self.assertEqual(self.repo.git("rev-parse", "master"), output["commit"])

    def test_merge_preserves_unrelated_untracked_files_on_master(self):
        (self.repo.root / "notes.txt").write_text("local notes\n")
        result = self.prepare()
        output = tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertTrue(output["local_master_synced"])
        self.assertEqual((self.repo.root / "notes.txt").read_text(), "local notes\n")

    def test_dirty_master_blocks_before_publication(self):
        result = self.prepare()
        (self.repo.root / "behavior.txt").write_text("user edits\n")
        with self.assertRaisesRegex(tool.ToolError, "has changes"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_diverged_master_blocks_before_publication(self):
        result = self.prepare()
        (self.repo.root / "user.txt").write_text("local work\n")
        self.repo.git("add", "user.txt")
        self.repo.git("commit", "-m", "Unpublished work")
        with self.assertRaisesRegex(tool.ToolError, "unpublished or diverged"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_changed_staged_preview_blocks_before_publication(self):
        result = self.prepare()
        checkout = Path(result["checkout"])
        (checkout / "behavior.txt").write_text("different\n")
        self.repo.git("add", "behavior.txt", cwd=checkout)
        with self.assertRaisesRegex(tool.ToolError, "staged tree changed"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_changed_preview_blocks_before_publication(self):
        result = self.prepare()
        (Path(result["checkout"]) / "behavior.txt").write_text("different\n")
        with self.assertRaisesRegex(tool.ToolError, "unstaged changes"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_changed_head_blocks_before_publication(self):
        result = self.prepare()
        self.api.pull["head"]["sha"] = "a" * 40
        with self.assertRaisesRegex(tool.ToolError, "head changed"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_ci_failure_blocks_before_publication(self):
        result = self.prepare()
        self.api.check_data["runs"] = [{"name": "test", "status": "completed", "conclusion": "failure"}]
        with self.assertRaisesRegex(tool.ToolError, "Check test"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_local_conflict_retains_snapshot_without_publication(self):
        (self.repo.root / "behavior.txt").write_text("conflicting master change\n")
        self.repo.git("commit", "-am", "Another fix on master")
        base = self.repo.git("rev-parse", "HEAD")
        self.repo.git("push", "origin", "master")
        self.api.pull["base"]["sha"] = base
        with self.assertRaisesRegex(tool.ToolError, "Snapshot retained at"):
            self.prepare()
        self.assertFalse(self.api.writes)
        self.assertEqual(self.repo.git("rev-parse", "HEAD"), base)
        self.assertTrue((self.directory / "snapshot" / "snapshot.json").exists())

    def test_changed_base_blocks_before_publication(self):
        result = self.prepare()
        self.api.pull["base"]["sha"] = "a" * 40
        with self.assertRaisesRegex(tool.ToolError, "base changed"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertFalse(self.api.writes)

    def test_sync_failure_retains_published_merge(self):
        result = self.prepare()
        with patch.object(tool, "sync_master", side_effect=tool.ToolError("Fetch failed")):
            output = tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        self.assertTrue(output["merged"])
        self.assertFalse(output["local_master_synced"])
        record = json.loads((Path(result["snapshot"]) / "snapshot.json").read_text())
        self.assertEqual(record["merge_result"]["sha"], output["commit"])
        synced = tool.resume_sync(self.repo, self.api, result["snapshot"])
        self.assertTrue(synced["local_master_synced"])
        self.assertEqual(len(self.api.writes), 1)
        # Repeating synchronization is safe and does not publish another commit.
        self.assertTrue(tool.resume_sync(self.repo, self.api, result["snapshot"])["local_master_synced"])

    def test_unknown_mutation_outcome_cannot_be_retried(self):
        result = self.prepare()
        with patch.object(self.api, "api", side_effect=tool.ToolError("Network failed; unknown outcome")):
            with self.assertRaisesRegex(tool.ToolError, "unknown outcome"):
                tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")
        with self.assertRaisesRegex(tool.ToolError, "already attempted"):
            tool.merge(self.repo, self.api, 1752, result["snapshot"], "Validated")

    def test_cleanup_refuses_untracked_work(self):
        result = self.snapshot()
        (Path(result["checkout"]) / "user.txt").write_text("retain me")
        with self.assertRaisesRegex(tool.ToolError, "untracked"):
            tool.cleanup(self.repo, result["snapshot"])
        self.assertTrue(Path(result["checkout"]).exists())


class RuleTests(unittest.TestCase):
    def test_invalid_credential_falls_back_only_for_public_reads(self):
        api = tool.GitHub(type("Repo", (), {})())
        api._loaded, api._token = True, "test-invalid-token"
        error = HTTPError("https://api.github.com/repos/example/repo/pulls", 401,
                          "Unauthorized", {}, io.BytesIO(b'{"message":"Bad credentials"}'))
        response = io.BytesIO(b'[{"number":1752}]')
        with patch.object(tool, "urlopen", side_effect=[error, response]) as opened:
            self.assertEqual(api.request("repos/example/repo/pulls"), [{"number": 1752}])
            self.assertIsNotNone(opened.call_args_list[0].args[0].get_header("Authorization"))
            self.assertIsNone(opened.call_args_list[1].args[0].get_header("Authorization"))

    def test_failed_write_is_never_retried_anonymously(self):
        api = tool.GitHub(type("Repo", (), {})())
        api._loaded, api._token = True, "test-invalid-token"
        error = HTTPError("https://api.github.com/repos/example/repo/pulls/1752/merge", 401,
                          "Unauthorized", {}, io.BytesIO(b'{"message":"Bad credentials"}'))
        with patch.object(tool, "urlopen", side_effect=error) as opened:
            with self.assertRaisesRegex(tool.ToolError, "refresh the Git credential"):
                api.request("repos/example/repo/pulls/1752/merge", "PUT", {"sha": "a" * 40})
            self.assertEqual(opened.call_count, 1)

    def test_pagination_collects_all_pages(self):
        api = tool.GitHub(type("Repo", (), {})())
        with patch.object(api, "api", side_effect=[list(range(100)), [100, 101]]) as call:
            self.assertEqual(len(api.pages("pulls", params={"state": "open"})), 102)
            self.assertIn("page=2", call.call_args.args[0])

    def test_draft_non_master_and_change_request_are_blockers(self):
        pr = {"state": "open", "draft": True, "base": {"ref": "other"}, "mergeable": True}
        checks = {"status": {"total_count": 0}, "runs": []}
        reviews = [{"id": 1, "state": "CHANGES_REQUESTED", "user": {"login": "reviewer"}},
                   {"id": 2, "state": "COMMENTED", "user": {"login": "reviewer"}}]
        self.assertEqual(len(tool.blockers(pr, checks, reviews)), 3)
        reviews.append({"id": 3, "state": "APPROVED", "user": {"login": "reviewer"}})
        self.assertEqual(len(tool.blockers(pr, checks, reviews)), 2)

    def test_pending_checks_are_blockers(self):
        pr = {"state": "open", "draft": False, "base": {"ref": "master"}, "mergeable": True}
        checks = {"status": {"total_count": 1, "state": "pending"},
                  "runs": [{"name": "test", "status": "in_progress", "conclusion": None}]}
        self.assertEqual(len(tool.blockers(pr, checks, [])), 2)


if __name__ == "__main__":
    unittest.main()
