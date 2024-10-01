from qfluentwidgets import FluentIcon

from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask

logger = get_logger(__name__)


class FarmWorldTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "Click Start in Game World"
        self.name = "Farm World Boss(Must Drop a WayPoint on the Boss First)"
        self.icon = FluentIcon.GLOBE

    def run(self):
        self.set_check_monthly_card()
        self.run_to_combat()

    def run_to_combat(self):
        self.run_until(self.check_health_bar, 'w', time_out=60, running=True)
        self.combat_once()
        self.run_in_circle_to_find_echo(3)
