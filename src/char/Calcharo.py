from src.char.BaseChar import BaseChar


class Calcharo(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.logger.debug('Calcharo wait intro animation')
            self.sleep(1)
            self.task.wait_in_team_and_world(time_out=3, raise_if_not_found=False)
            self.check_combat()
        super().do_perform()
