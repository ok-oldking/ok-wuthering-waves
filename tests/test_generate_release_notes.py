import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / ".github" / "scripts" / "generate_release_notes.py"

spec = importlib.util.spec_from_file_location("generate_release_notes", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestGenerateReleaseNotes(unittest.TestCase):
    def test_extract_changelog_section_matches_tag_variants(self):
        text = (
            "# Changelog\n\n"
            "## v3.8.4 (2026-11-18)\n\n"
            "- Item A\n"
            "- Item B\n\n"
            "## [3.8.3] - 2026-11-15\n"
            "- Item C\n"
        )
        self.assertEqual(mod.extract_changelog_section(text, "v3.8.4"), "- Item A\n- Item B")
        self.assertEqual(mod.extract_changelog_section(text, "3.8.4"), "- Item A\n- Item B")
        self.assertEqual(mod.extract_changelog_section(text, "v3.8.3"), "- Item C")
        self.assertIsNone(mod.extract_changelog_section(text, "v9.9.9"))

    def test_build_release_notes_from_repo_changelogs(self):
        notes = mod.build_release_notes(
            tag="v3.8.4",
            en_changelog=ROOT / "CHANGELOG.md",
            zh_changelog=ROOT / "CHANGELOG.zh-CN.md",
        )
        self.assertIn("### Changelog (English)", notes)
        self.assertIn("Restored cloud browser play at 1080p", notes)
        self.assertIn("### 更新日志 (中文)", notes)
        self.assertIn("恢复 1080p 网页云游戏支持", notes)
        self.assertIn("### Install from source", notes)

    def test_build_release_notes_falls_back_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            en_file = tmp_path / "CHANGELOG.md"
            zh_file = tmp_path / "CHANGELOG.zh-CN.md"
            en_file.write_text("# Changelog\n", encoding="utf-8")
            zh_file.write_text("# Changelog\n", encoding="utf-8")

            notes = mod.build_release_notes(
                tag="v9.9.9",
                en_changelog=en_file,
                zh_changelog=zh_file,
                fallback_changes="* Some commit",
                start_tag="v3.8.3",
                end_tag="v3.8.4",
            )
            self.assertIn("### 更新日志 v3.8.3 -> v3.8.4", notes)
            self.assertIn("* Some commit", notes)
            self.assertNotIn("### Changelog (English)", notes)


if __name__ == "__main__":
    unittest.main()
