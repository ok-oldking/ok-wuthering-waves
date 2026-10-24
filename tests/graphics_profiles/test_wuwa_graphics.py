import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from src.graphics_profiles import profiles as graphics


class GraphicsTests(unittest.TestCase):
    def setUp(self):
        self.idle_patch = patch.object(graphics, "ensure_idle", return_value=None)
        self.idle_patch.start()
        self.addCleanup(self.idle_patch.stop)

    def test_game_starts_after_backup_before_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            original = b"[ScalabilityGroups]\nsg.ShadowQuality=3\n"
            ini.write_bytes(original)
            with (
                patch.object(
                    graphics,
                    "ensure_idle",
                    side_effect=[None, RuntimeError("game started")],
                ),
                self.assertRaisesRegex(RuntimeError, "game started"),
            ):
                graphics.apply_profile(
                    {
                        "db": {"ImageQuality": "0"},
                        "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
                    },
                    dbpath,
                    ini,
                    Path(folder) / "backup",
                )
            self.assertEqual(ini.read_bytes(), original)
            self.assertEqual(
                graphics.read_graphics(dbpath, ini)["db"]["ImageQuality"], "3"
            )
            self.assertEqual(len(list((Path(folder) / "backup").glob("*.json"))), 1)

    def test_game_starts_before_ini_commit_database_transaction_unwinds(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            original = b"[ScalabilityGroups]\nsg.ShadowQuality=3\n"
            ini.write_bytes(original)
            with (
                patch.object(
                    graphics,
                    "ensure_idle",
                    side_effect=[None, None, RuntimeError("game started at INI")],
                ),
                self.assertRaisesRegex(RuntimeError, "game started at INI"),
            ):
                graphics.apply_profile(
                    {
                        "db": {"ImageQuality": "0"},
                        "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
                    },
                    dbpath,
                    ini,
                )
            self.assertEqual(ini.read_bytes(), original)
            self.assertEqual(
                graphics.read_graphics(dbpath, ini)["db"]["ImageQuality"], "3"
            )

    def test_game_running_before_readback_rollback_preserves_committed_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            ini.write_bytes(b"[ScalabilityGroups]\nsg.ShadowQuality=3\n")
            real_read = graphics.read_graphics
            calls = []

            def read(*args):
                calls.append(1)
                if len(calls) == 2:
                    raise OSError("readback failed after commit")
                return real_read(*args)

            with (
                patch.object(graphics, "read_graphics", side_effect=read),
                patch.object(
                    graphics,
                    "ensure_idle",
                    side_effect=[None, None, None, RuntimeError("game now running")],
                ),
                self.assertRaisesRegex(RuntimeError, "无法安全回滚"),
            ):
                graphics.apply_profile(
                    {
                        "db": {"ImageQuality": "0"},
                        "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
                    },
                    dbpath,
                    ini,
                    Path(folder) / "backup",
                )
            self.assertEqual(real_read(dbpath, ini)["db"]["ImageQuality"], "0")
            self.assertIn(b"sg.ShadowQuality=0", ini.read_bytes())
            self.assertTrue(list((Path(folder) / "backup").glob("*.ini")))

    def test_post_commit_readback_failure_restores_original(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            original = b"[ScalabilityGroups]\r\nsg.ShadowQuality=3\r\n"
            ini.write_bytes(original)
            real_read = graphics.read_graphics
            calls = []

            def read(*args):
                calls.append(1)
                if len(calls) == 2:
                    raise OSError("simulated readback unavailable")
                return real_read(*args)

            with (
                patch.object(graphics, "read_graphics", side_effect=read),
                self.assertRaisesRegex(RuntimeError, "已回滚"),
            ):
                graphics.apply_profile(
                    {
                        "db": {"ImageQuality": "0"},
                        "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
                    },
                    dbpath,
                    ini,
                )
            self.assertEqual(ini.read_bytes(), original)
            self.assertEqual(real_read(dbpath, ini)["db"]["ImageQuality"], "3")

    def test_foreign_post_commit_edit_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            ini.write_bytes(b"[ScalabilityGroups]\nsg.ShadowQuality=3\n")
            real_read = graphics.read_graphics
            calls = []

            def read(*args):
                calls.append(1)
                if len(calls) == 2:
                    with closing(sqlite3.connect(dbpath)) as db, db:
                        db.execute(
                            "UPDATE LocalStorage SET Value='2' WHERE Key='ImageQuality'"
                        )
                return real_read(*args)

            with (
                patch.object(graphics, "read_graphics", side_effect=read),
                self.assertRaisesRegex(RuntimeError, "无法安全回滚"),
            ):
                graphics.apply_profile(
                    {
                        "db": {"ImageQuality": "0"},
                        "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
                    },
                    dbpath,
                    ini,
                )
            self.assertEqual(real_read(dbpath, ini)["db"]["ImageQuality"], "2")

    def test_snapshot_existence_is_not_native_readback(self):
        profile = {
            "db": {"ImageQuality": "0"},
            "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
        }
        actual = {
            "db": {"ImageQuality": "0"},
            "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
            "other": "ignored",
        }
        self.assertEqual(graphics.profile_mismatches(profile, actual), [])
        actual["db"]["ImageQuality"] = "3"
        self.assertEqual(
            graphics.profile_mismatches(profile, actual), ["db:ImageQuality"]
        )
        actual["ini"]["ScalabilityGroups"].clear()
        self.assertEqual(
            graphics.profile_mismatches(profile, actual),
            ["db:ImageQuality", "ini:ScalabilityGroups:sg.ShadowQuality"],
        )

    def test_only_graphics_change_and_non_graphics_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.executemany(
                    "INSERT INTO LocalStorage VALUES(?,?)",
                    [
                        ("ImageQuality", "3"),
                        ("ShadowQuality", "3"),
                        ("CameraSensitivity", "80"),
                        ("Account", "untouched"),
                    ],
                )
            ini.write_bytes(
                b"[ScalabilityGroups]\r\nsg.ShadowQuality=3\r\n[/Script/Engine.GameUserSettings]\r\nFrameRateLimit=60\r\nResolutionSizeX=3840\r\nAudioQualityLevel=0\r\n"
            )
            profile = {
                "db": {"ImageQuality": "0", "ShadowQuality": "0"},
                "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
            }
            graphics.apply_profile(profile, dbpath, ini)
            with closing(sqlite3.connect(dbpath)) as db, db:
                rows = dict(db.execute("SELECT Key,Value FROM LocalStorage"))
            self.assertEqual(
                rows,
                {
                    "ImageQuality": "0",
                    "ShadowQuality": "0",
                    "CameraSensitivity": "80",
                    "Account": "untouched",
                },
            )
            self.assertIn(
                b"ResolutionSizeX=3840\r\nAudioQualityLevel=0", ini.read_bytes()
            )
            self.assertIn(b"sg.ShadowQuality=0\r\n", ini.read_bytes())

    def test_unknown_ini_key_rejected(self):
        with self.assertRaises(RuntimeError):
            graphics.patch_ini("[A]\nx=1\n", {"A": {"y": "2"}})

    def test_duplicate_ini_key_rejected(self):
        with self.assertRaises(RuntimeError):
            graphics.patch_ini("[A]\nx=1\nx=1\n", {"A": {"x": "2"}})

    def test_account_or_resolution_write_rejected(self):
        for p in (
            {"db": {"Account": "new"}, "ini": {}},
            {
                "db": {},
                "ini": {"/Script/Engine.GameUserSettings": {"ResolutionSizeX": "1"}},
            },
        ):
            with self.assertRaises(RuntimeError):
                graphics.apply_profile(p, None, None)

    def test_missing_db_row_rolls_back_without_ini_change(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "test.db"
            ini = Path(folder) / "test.ini"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY,Value TEXT)")
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            original = b"[ScalabilityGroups]\nsg.ShadowQuality=3\n"
            ini.write_bytes(original)
            with self.assertRaises(RuntimeError):
                graphics.apply_profile(
                    {
                        "db": {"ImageQuality": "0", "ShadowQuality": "0"},
                        "ini": {"ScalabilityGroups": {"sg.ShadowQuality": "0"}},
                    },
                    dbpath,
                    ini,
                )
            self.assertEqual(ini.read_bytes(), original)
            with closing(sqlite3.connect(dbpath)) as db:
                self.assertEqual(
                    db.execute("SELECT Value FROM LocalStorage").fetchone()[0], "3"
                )


if __name__ == "__main__":
    unittest.main()
