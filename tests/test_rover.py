import unittest

from src.char.BaseChar import Elements
from src.char.Rover import Rover


class RoverInitializationTest(unittest.TestCase):
    def test_wind_team_state_initializes_when_form_is_already_known(self):
        class Task:
            _app = None

            def has_char(self, char_class):
                return char_class.__name__ in {'Cartethyia', 'Phoebe'}

        task = Task()
        rover = Rover(task, 0, ring_index=Elements.WIND)

        rover.init()

        self.assertTrue(rover.use_skyfall_severance)


if __name__ == '__main__':
    unittest.main()
