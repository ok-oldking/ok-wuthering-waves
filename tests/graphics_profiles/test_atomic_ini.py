"""真实 SQLite+INI 事务中的半写入、替换失败及外部更新回归。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
from unittest.mock import patch
import sqlite3
import unittest
from src.graphics_profiles import profiles as graphics


class AtomicIniTests(unittest.TestCase):
    def test_partial_staging_write_does_not_truncate_live_ini(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ini, dbpath = root / 'settings.ini', root / 'settings.db'
            original = b'[ScalabilityGroups]\nsg.ShadowQuality=3\n[Other]\nAudio=1\n'
            ini.write_bytes(original)
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute('CREATE TABLE LocalStorage(Key TEXT PRIMARY KEY, Value TEXT)')
                db.execute("INSERT INTO LocalStorage VALUES('ImageQuality','3')")
            profile = {'db': {'ImageQuality': '0'}, 'ini': {'ScalabilityGroups': {'sg.ShadowQuality': '0'}}}
            write = graphics.write_staged
            def fail_halfway(stream, data):
                if str(stream.name).endswith('.tmp'):
                    stream.write(data[:15]); stream.flush()
                    raise OSError('partial disk write')
                write(stream, data)
            with patch.object(graphics, 'write_staged', side_effect=fail_halfway), self.assertRaises(OSError):
                graphics.apply_profile(profile, dbpath, ini, idle=lambda: None)
            self.assertEqual(ini.read_bytes(), original)
            self.assertEqual(graphics.read_graphics(dbpath, ini)['db']['ImageQuality'], '3')
            self.assertEqual(next((root / 'graphics-profile-backups').glob('*.ini')).read_bytes(), original)
            self.assertFalse(list(root.glob('*.tmp')))

    def test_failed_replace_and_foreign_edit_preserve_live_file(self):
        with TemporaryDirectory() as temporary:
            file = Path(temporary) / 'settings.ini'
            file.write_bytes(b'old')
            with patch.object(graphics.os, 'replace', side_effect=OSError('replace')), self.assertRaises(OSError):
                graphics.atomic_ini(file, b'new', (b'old',))
            self.assertEqual(file.read_bytes(), b'old')
            with self.assertRaises(RuntimeError):
                graphics.atomic_ini(file, b'new', (b'foreign',))
            self.assertEqual(file.read_bytes(), b'old')
            self.assertFalse(list(file.parent.glob('*.tmp')))
