from pathlib import Path

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.Labels import Labels
from src.char.BaseChar import CharType, Elements
from src.char.CharFactory import get_char_by_pos
from src.char.Hiyuki import Hiyuki
from src.task.AutoCombatTask import AutoCombatTask


ROOT = Path(__file__).resolve().parents[1]


class TestHiyukiSkin(TaskTestCase):
    task_class = AutoCombatTask
    config = {**config, 'template_matching': dict(config['template_matching'])}

    def test_both_portraits_resolve_to_canonical_hiyuki(self):
        for image in ('hiyuki1.png', 'hiyuki3.png', 'hiyuki-skin.png', 'hiyuki-skin-inactive.png'):
            with self.subTest(image=image):
                self.set_image(str(ROOT / 'ok_templates' / image))
                char = get_char_by_pos(self.task, self.task.get_box_by_name('box_char_1'), 0, None)
                self.assertIsInstance(char, Hiyuki)
                self.assertEqual(char.char_name, Labels.char_hiyuki)
                self.assertEqual(char.char_type, CharType.MAIN_DPS)
                self.assertEqual(char.ring_index, Elements.ICE)

    def test_cached_hiyuki_recognizes_new_skin(self):
        self.set_image(str(ROOT / 'ok_templates/hiyuki-skin.png'))
        old = Hiyuki(self.task, 0, char_name=Labels.char_hiyuki, confidence=0.99,
                     ring_index=Elements.ICE)
        char = get_char_by_pos(self.task, self.task.get_box_by_name('box_char_1'), 0, old)
        self.assertIs(char, old)
        self.assertEqual(char.char_name, Labels.char_hiyuki)
        self.assertEqual(char.ring_index, Elements.ICE)
        self.assertEqual(char.char_type, CharType.MAIN_DPS)

    def test_new_portrait_does_not_match_other_occupied_slots(self):
        for image in ('hiyuki-skin.png', 'hiyuki-skin-inactive.png'):
            self.set_image(str(ROOT / 'ok_templates' / image))
            for slot in (2, 3):
                with self.subTest(image=image, slot=slot):
                    self.assertIsNone(self.task.find_one(
                        Labels.char_hiyuki2, box=self.task.get_box_by_name(f'box_char_{slot}'), threshold=0.6))
