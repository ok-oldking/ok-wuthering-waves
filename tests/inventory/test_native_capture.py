"""原生截图读取边界测试，不操作游戏。"""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from src.inventory_support import inventory_native_capture as capture
from src.inventory_support import inventory_observation as observation

class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.capture=capture
        self.observation=observation
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        import numpy as np
        self.frame=np.zeros((1080,1920,3),dtype=np.uint8)
        self.cfg={'materials':[dict(id='material',name='材料',category='skill',
                  label_roi=[0,0,100,40],quantity_roi=[100,0,40,40])],
                  'page_anchor':dict(text='资源',roi=[0,40,100,40]),
                  'game_exe_sha256':'a'*64,'resource_fingerprints':{'version':'b'*64},'scope':'selected'}
        self.probe=SimpleNamespace(load_calibration=lambda *a:self.cfg,
            check_calibration_sources=lambda *a:None,compact=lambda x:''.join(x.split()),
            file_sha256=lambda f:'a'*64,observation=self.observation,
            verified_pair=lambda frames:len(frames)==2,atomic_json=lambda *a:None)

    def run_capture(self, count='68', name='材料', guard=lambda:None, selected_ids=None):
        def read(roi, frame):
            return {'text':count if roi==[100,0,40,40] else '资源' if roi==[0,40,100,40] else name,
                    'confidence':.99}
        port=SimpleNamespace(_frame=lambda:self.frame.copy(),_read=read)
        return self.capture.collect_page(port,'wuwa',{'pid':1,'path':'native'},'calibration',
            10,probe=self.probe,folder=Path(self.temp.name)/'capture',guard=guard,pause=lambda _:None,selected_ids=selected_ids)

    def test_large_page_reads_only_selected_material(self):
        self.cfg['scope'] = 'selected_materials_only'
        self.cfg['materials'] += [dict(self.cfg['materials'][0], id=f'extra-{i}') for i in range(90)]
        result = self.run_capture(selected_ids=['material'])
        result['game_identity']['created'] = '2026-10-14T00:00:00+00:00'
        self.assertEqual([row['id'] for row in result['materials']], ['material'])
        merged = self.observation.merge_reports('wuwa', [result])
        self.assertEqual(len(merged['materials']), 1)

    def test_unknown_selected_material_rejected(self):
        with self.assertRaises(ValueError):
            self.run_capture(selected_ids=['absent'])

    def test_native_ocr_two_frames_confirm_exact_count(self):
        result=self.run_capture()
        self.assertEqual(result['materials'][0]['quantity'],68)
        self.assertEqual(result['materials'][0]['status'],'confirmed')

    def test_short_count_is_unknown_not_zero(self):
        result=self.run_capture(count='1.2万')
        self.assertNotEqual(result['materials'][0]['status'],'confirmed')
        self.assertIsNone(result['materials'][0]['quantity'])

    def test_wrong_material_never_confirms(self):
        result=self.run_capture(name='别的材料')
        self.assertNotEqual(result['materials'][0]['status'],'confirmed')

    def test_guard_failure_stops_capture(self):
        def fail():
            raise RuntimeError('paused')
        with self.assertRaisesRegex(RuntimeError,'paused'):
            self.run_capture(guard=fail)


if __name__=='__main__':
    unittest.main()
