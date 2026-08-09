import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / ".github" / "scripts" / "extract_issue_log.py"
SPEC = importlib.util.spec_from_file_location("extract_issue_log", SCRIPT_PATH)
extract_issue_log = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(extract_issue_log)


class ExtractIssueLogTest(unittest.TestCase):
    def test_accepts_expected_github_attachment_url(self):
        url = "https://github.com/user-attachments/files/30814966/OK-WW-log.zip"
        self.assertEqual(url, extract_issue_log.validate_attachment_url(url))

    def test_rejects_non_github_and_lookalike_urls(self):
        invalid_urls = [
            "http://github.com/user-attachments/files/30814966/OK-WW-log.zip",
            "https://example.com/user-attachments/files/30814966/OK-WW-log.zip",
            "https://github.com.evil.test/user-attachments/files/30814966/OK-WW-log.zip",
            "https://github.com/user-attachments/files/not-an-id/OK-WW-log.zip",
            "https://github.com/user-attachments/files/30814966/other.zip",
        ]
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(extract_issue_log.UnsafeArchiveError):
                extract_issue_log.validate_attachment_url(url)

    def test_extracts_log_and_supported_screenshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "archive.zip"
            output_root = root / "output"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("OK-WW-log/logs/ok-script.log", "diagnostic log\n")
                archive.writestr(
                    "OK-WW-log/screenshots/task/first.png",
                    b"\x89PNG\r\n\x1a\nimage data",
                )
                archive.writestr(
                    "OK-WW-log/screenshots/second.jpg", b"\xff\xd8\xffimage data"
                )
                archive.writestr("OK-WW-log/screenshots/ignored.txt", "not an image")
                archive.writestr("OK-WW-log/notes.txt", "must not be extracted")

            log, screenshots = extract_issue_log.extract_archive(archive_path, output_root)

            self.assertEqual(output_root / "logs" / "ok-script.log", log)
            self.assertEqual("diagnostic log\n", log.read_text())
            self.assertEqual(
                {
                    output_root / "screenshots" / "task" / "first.png",
                    output_root / "screenshots" / "second.jpg",
                },
                set(screenshots),
            )
            self.assertFalse((output_root / "screenshots" / "ignored.txt").exists())
            self.assertFalse((output_root / "notes.txt").exists())
            diagnostics = json.loads(
                (output_root / "diagnostics.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(diagnostics["app_version"])
            self.assertIsNone(diagnostics["resolution"])
            manifest = json.loads(
                (output_root / "screenshots-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(2, manifest["total_extracted"])
            self.assertEqual(8, manifest["analysis_limit"])
            self.assertEqual(
                {"screenshots/task/first.png", "screenshots/second.jpg"},
                set(manifest["analysis_candidates"]),
            )

    def test_parses_last_version_profile_pyappify_and_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "ok-script.log"
            log_path.write_text(
                "\n".join(
                    [
                        "pyappify app_version:v3.5.20, app_profile:Global, "
                        "pyappify_version:1.1.8 pyappify_upgradeable:False, "
                        "pyappify_executable:C:\\old.exe",
                        "DeviceManager:update_pc_device pc_device: "
                        "{'width': 1280, 'height': 720, 'full_path': 'private'}",
                        "pyappify app_version:*v3.5.27*, app_profile:China, "
                        "pyappify_version:*1*.*1*.*9* pyappify_upgradeable:True, "
                        "pyappify_executable:D:\\ok-ww\\ok-ww.exe",
                        "DeviceManager:update_pc_device pc_device: "
                        "{'width': *1920*, 'height': *1080*, "
                        "'full_path': 'E:\\\\Games\\\\private.exe'}",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = extract_issue_log.parse_log_diagnostics(log_path)

            self.assertEqual("v3.5.27", diagnostics["app_version"])
            self.assertEqual("China", diagnostics["app_profile"])
            self.assertEqual("1.1.9", diagnostics["pyappify_version"])
            self.assertIs(True, diagnostics["pyappify_upgradeable"])
            self.assertEqual(
                {"width": 1920, "height": 1080}, diagnostics["resolution"]
            )
            self.assertEqual(
                {"app_metadata": 3, "device_manager": 4},
                diagnostics["source_lines"],
            )

    def test_normalizes_unavailable_metadata_to_null(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "ok-script.log"
            log_path.write_text(
                "pyappify app_version:None, app_profile:null, "
                "pyappify_version:*None* pyappify_upgradeable:False\n",
                encoding="utf-8",
            )

            diagnostics = extract_issue_log.parse_log_diagnostics(log_path)

            self.assertIsNone(diagnostics["app_version"])
            self.assertIsNone(diagnostics["app_profile"])
            self.assertIsNone(diagnostics["pyappify_version"])
            self.assertIs(False, diagnostics["pyappify_upgradeable"])

    def test_limits_screenshot_analysis_candidates_but_extracts_all(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "archive.zip"
            output_root = root / "output"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("logs/ok-script.log", "log")
                for index in range(10):
                    info = zipfile.ZipInfo(f"screenshots/{index:02}.png")
                    info.date_time = (2026, 1, index + 1, 0, 0, 0)
                    archive.writestr(info, b"\x89PNG\r\n\x1a\nimage data")

            _, screenshots = extract_issue_log.extract_archive(
                archive_path, output_root
            )
            manifest = json.loads(
                (output_root / "screenshots-manifest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(10, len(screenshots))
            self.assertEqual(10, manifest["total_extracted"])
            self.assertEqual(8, len(manifest["analysis_candidates"]))
            self.assertEqual("screenshots/09.png", manifest["analysis_candidates"][0])
            self.assertEqual("screenshots/02.png", manifest["analysis_candidates"][-1])

    def test_rejects_log_outside_logs_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("ok-script.log", "wrong location")

            with self.assertRaisesRegex(
                extract_issue_log.UnsafeArchiveError, "logs/ok-script.log"
            ):
                extract_issue_log.extract_archive(
                    archive_path, Path(directory) / "output"
                )

    def test_rejects_multiple_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("a/logs/ok-script.log", "first")
                archive.writestr("b/logs/OK-SCRIPT.LOG", "second")

            with self.assertRaisesRegex(
                extract_issue_log.UnsafeArchiveError, "multiple logs/ok-script.log"
            ):
                extract_issue_log.extract_archive(
                    archive_path, Path(directory) / "output"
                )

    def test_rejects_unsafe_archive_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("logs/ok-script.log", "log")
                archive.writestr("screenshots/../escape.png", b"\x89PNG\r\n\x1a\n")

            with self.assertRaisesRegex(
                extract_issue_log.UnsafeArchiveError, "unsafe path"
            ):
                extract_issue_log.extract_archive(
                    archive_path, Path(directory) / "output"
                )

    def test_rejects_image_with_invalid_content(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("logs/ok-script.log", "log")
                archive.writestr("screenshots/not-really.png", "plain text")

            with self.assertRaisesRegex(
                extract_issue_log.UnsafeArchiveError, "invalid .png content"
            ):
                extract_issue_log.extract_archive(
                    archive_path, Path(directory) / "output"
                )

    def test_failed_download_removes_stale_log(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "output"
            output_root.mkdir()
            (output_root / "stale.log").write_text("log from a previous issue")
            with mock.patch.object(
                extract_issue_log,
                "download_archive",
                side_effect=extract_issue_log.UnsafeArchiveError("download failed"),
            ):
                with self.assertRaises(extract_issue_log.UnsafeArchiveError):
                    extract_issue_log.download_and_extract(
                        "https://github.com/user-attachments/files/30814966/OK-WW-log.zip",
                        output_root,
                    )
            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
