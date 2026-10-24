"""更新随包资源时不覆盖用户数据，失败时保留旧资源。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from src.inventory_support import runtime


class ResourceTests(unittest.TestCase):
    def test_resource_refresh_and_no_user_config_changes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / 'assets', root / 'config'
            source.mkdir()
            target.mkdir()
            (source / 'recipe.json').write_bytes(b'new')
            (target / 'recipe.json').write_bytes(b'old')
            (target / 'user-targets.json').write_bytes(b'user')
            runtime.sync_assets(source, target)
            self.assertEqual((target / 'recipe.json').read_bytes(), b'new')
            self.assertEqual((target / 'user-targets.json').read_bytes(), b'user')
            stamp = (target / 'recipe.json').stat().st_mtime_ns
            runtime.sync_assets(source, target)
            self.assertEqual((target / 'recipe.json').stat().st_mtime_ns, stamp)
            (source / 'recipe.json').write_bytes(b'next')
            with patch.object(runtime.os, 'replace', side_effect=OSError('disk')), self.assertRaises(OSError):
                runtime.sync_assets(source, target)
            self.assertEqual((target / 'recipe.json').read_bytes(), b'new')
            self.assertFalse(list(target.glob('*.tmp')))
