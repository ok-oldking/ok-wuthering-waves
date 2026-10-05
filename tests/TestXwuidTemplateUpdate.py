import copy
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.update_xwuid_echo_templates import (
    differences, git, read_resources, snapshot_bytes, sync_and_zip,
    validate_template, write_if_changed, main,
)


def template(name="测试-通用", attack=1.0):
    return {
        "name": name,
        "main_props": {str(cost): {"攻击%": attack} for cost in (1, 3, 4)},
        "sub_props": {"攻击%": attack},
        "skill_weight": [0.5, 0, 0.25, 0],
        "score_max": [70, 75, 80],
    }


class TestXwuidTemplateUpdate(unittest.TestCase):
    def test_new_resource_commit_without_weight_change_skips_release(self):
        data = {"templates": {"default": {"default": template("角色-通用")}}, "conditions": {}}
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / ".git").mkdir()
            snapshot = repo / "snapshot.py"
            previous = snapshot_bytes("a" * 40, data)
            snapshot.write_bytes(previous)
            with patch("scripts.update_xwuid_echo_templates.SNAPSHOT", snapshot), \
                    patch("scripts.update_xwuid_echo_templates.require_clean"), \
                    patch("scripts.update_xwuid_echo_templates.read_resources", return_value=("b" * 40, data)), \
                    patch("scripts.update_xwuid_echo_templates.publish") as publish:
                self.assertEqual(0, main(["--no-fetch", "--publish", "--distribution", str(repo)]))
            self.assertEqual(previous, snapshot.read_bytes())
            publish.assert_not_called()

    def test_new_and_changed_modal_templates_and_removed_weights(self):
        before = {"templates": {"default": {"default": template("角色-通用")},
                  "1111": {"default": template()}, "2222": {"default": template("旧角色")}},
                  "conditions": {}}
        after = copy.deepcopy(before)
        after["templates"]["1111"]["default"]["sub_props"]["攻击%"] = 1.5
        after["templates"]["1111"]["phantom"] = template("测试-声骸")
        after["templates"]["3333"] = {"default": template("新角色-通用")}
        del after["templates"]["2222"]
        after["conditions"]["1111"] = [{"choose": "calc-phantom.json"}]

        result = differences(before, after)

        self.assertEqual(["测试-声骸", "新角色-通用"], result["added"])
        self.assertEqual(["测试-通用"], result["updated"])
        self.assertEqual(["旧角色"], result["removed"])
        self.assertTrue(result["conditions_changed"])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.py"
            content = snapshot_bytes("a" * 40, after)
            self.assertTrue(write_if_changed(path, content))
            stamp = path.stat().st_mtime_ns
            self.assertFalse(write_if_changed(path, snapshot_bytes("a" * 40, after)))
            self.assertEqual(stamp, path.stat().st_mtime_ns)
            loaded = runpy.run_path(str(path))
            self.assertEqual(after["templates"], loaded["TEMPLATES"])
            self.assertEqual(after["conditions"], loaded["CONDITIONS"])

    def test_reads_all_tracked_roles_and_ignores_untracked_calc(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            git(repo, "init", "--quiet")
            root = repo / "XutheringWavesUID/resource/map/character"
            for char, filename, payload in (
                ("default", "calc.json", template("角色-通用")),
                ("1111", "calc.json", template()),
                ("1111", "calc-phantom.json", template("测试-声骸")),
                ("1111", "condition.json", [{"choose": "calc-phantom.json"}]),
            ):
                path = root / char / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "-c", "user.name=Tests", "-c", "user.email=tests@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")
            (root / "1111" / "calc-untracked.json").write_text("{}", encoding="utf-8")

            commit, data = read_resources(repo)

            self.assertEqual(40, len(commit))
            self.assertEqual({"default", "1111"}, set(data["templates"]))
            self.assertEqual({"default", "phantom"}, set(data["templates"]["1111"]))
            self.assertEqual([{ "choose": "calc-phantom.json"}], data["conditions"]["1111"])

    def test_rejects_invalid_weights_and_missing_scoring_fields(self):
        for value in (float("nan"), float("inf"), -1, "1.0"):
            invalid = template(attack=value)
            with self.assertRaises(ValueError):
                validate_template(invalid, "calc.json")
        invalid = template()
        invalid["score_max"] = [0, 70, 80]
        with self.assertRaises(ValueError):
            validate_template(invalid, "calc.json")

    def test_sync_zip_excludes_cache_and_keeps_user_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            source.mkdir()
            (source / "module.py").write_bytes(b"# template\n")
            (source / "__pycache__").mkdir()
            (source / "__pycache__/module.pyc").write_bytes(b"cache")
            target = base / "target"
            target.mkdir()
            (target / "user.json").write_bytes(b"keep")
            archive_path = base / "echo-score.zip"

            sync_and_zip(source, [target], ["module.py"], archive_path)

            self.assertEqual(b"keep", (target / "user.json").read_bytes())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(["echo-score/module.py"], archive.namelist())
                self.assertEqual(b"# template\n", archive.read("echo-score/module.py"))
            first = archive_path.read_bytes()
            sync_and_zip(source, [target], ["module.py"], archive_path)
            self.assertEqual(first, archive_path.read_bytes())
