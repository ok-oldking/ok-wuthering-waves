import re
from qfluentwidgets import FluentIcon
from ok import Logger, Box, find_color_rectangles
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetDiscordNestTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        #
        self.name = "Tacet Discord Nest Task"
        self.description = "Auto Farm All Tacet Discord Nest"
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME
        self.icon = FluentIcon.CALORIES
        #
        self.tdn = [
            {"direction": "w", 'running_time': 4, "index": {"zh_CN": "复生丘原残象聚落", "zh_TW": "複生丘原殘象聚落", "en_US": "RebirthUplandsTacetDiscordNest"}},
            {"direction": "w", 'running_time': 6, "index": {"zh_CN": "陷足流川残象聚落", "zh_TW": "陷足流川殘象聚落", "en_US": "StagnantRunTacetDiscordNest"}},
        ]  # tips: new tacet discord nest can be added here

    def run(self):
        mission_list = self.prepare(scoll_bar_y=0)
        self.execute(scoll_bar_y=0, mission_list=mission_list)
        # tips: if more than one page, add new statement(s) with parameter `scoll_bar_y` as following
        #
        # mission_list = self.prepare(scoll_bar_y=0.5)
        # self.execute(scoll_bar_y=0.5, mission_list=mission_list)

    def prepare(self, skip_collected = True, scoll_bar_y = 0):
        self.info_set("mission", f"(preparing...)")
        self.ensure_main(time_out=180)
        gray_book_boss = self.openF2Book("gray_book_boss")
        self.click_box(gray_book_boss, after_sleep=1)
        self.click_relative(0.18, 0.78, after_sleep=1)  # Tacet Discord Nest
        #
        if (scoll_bar_y > 0):  # click scollbar
            self.click_relative(0.98, scoll_bar_y, after_sleep=1)
        frame_width = self.frame.shape[1]
        frame_height = self.frame.shape[0] 
        go_box_list = find_color_rectangles(
            image=self.frame,
            color_range={
                'r': (0, 72),
                'g': (0, 72),
                'b': (0, 72),
            },
            min_width=0.13 * frame_width,
            min_height=0.05 * frame_height,
            box=Box(
                x=frame_width*0.82,
                y=frame_height*0.18,
                to_x=frame_width*0.97,
                to_y=frame_height*0.93,
            )
        )
        if (not isinstance(go_box_list, list) or len(go_box_list) <= 0):
            raise "go button not found"
        counter_regex = re.compile(r"(\d{1,2})/(\d{1,2})")
        missionList = []
        for go_box in go_box_list:
            center = go_box.center()
            x = center[0] / frame_width
            y = center[1] / frame_height
            # counter
            counter_box = self.ocr(x=0.435, y=y+0.01, to_x=0.61, to_y=y+0.065, match=counter_regex, frame=self.frame)
            if (not isinstance(counter_box, list) or len(counter_box) <= 0):
                continue
            # name (without space)
            name_box = self.ocr(x=0.435, y=y-0.065, to_x=0.61, to_y=y, frame=self.frame)
            if (not isinstance(name_box, list) or len(name_box) <= 0):
                continue
            name = "".join("".join(list(map(lambda bb: bb.name, name_box))).split())
            if name == "":
                self.log_warn(f"prepare | name of tacet discord nest unrecognized")
            #
            for match in re.finditer(counter_regex, counter_box[0].name):
                numerator = match.group(1)
                denominator = match.group(2)
                if numerator != denominator or not skip_collected:
                    missionList.append({ "entry": [x, y], "name": name })
        #
        self.ensure_main(time_out=180)
        return missionList
    
    def execute(self, scoll_bar_y = 0, mission_list = []):
        if (not isinstance(mission_list, list) or len(mission_list) <= 0):
            self.info_set("mission", f"(empty)")
            return
        for mission in mission_list:
            self.info_set("mission", f"{mission.get("name")}")
            self.ensure_main(time_out=180)
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            self.click_relative(0.18, 0.78, after_sleep=1)  # Tacet Discord Nest
            if (scoll_bar_y > 0):  # click scollbar
                self.click_relative(0.98, scoll_bar_y, after_sleep=1)
            self.click_relative(mission.get("entry")[0], mission.get("entry")[1], after_sleep=1)  # Go
            self.sleep(1)
            self.click_relative(0.93, 0.90, after_sleep=1)  # Fast Travel
            self.wait_in_team_and_world(time_out=180)
            #
            tdn_found = False
            for t in self.tdn:
                if t.get("index")[self.game_lang] == mission.get("name"):
                    tdn_found = True
                    # move to combat zone
                    self.run_until(lambda: False, t.get('direction'), t.get('running_time'), running=True)
                    # combat
                    self.wait_until(self.in_combat, post_action=self.middle_click, time_out=10)
                    if self.in_combat():
                        self.combat_once(wait_combat_time=0, raise_if_not_found=False)
                    # collect echo
                    self.log_info('execute | collect echo')
                    collected = self.walk_find_echo(time_out=10, backward_time=5)
                    if not collected:
                        # teleport and collect echo again
                        self.ensure_main(time_out=180)
                        gray_book_boss = self.openF2Book("gray_book_boss")
                        self.click_box(gray_book_boss, after_sleep=1)
                        self.click_relative(0.18, 0.78, after_sleep=1)  # Tacet Discord Nest
                        if (scoll_bar_y > 0):  # click scollbar
                            self.click_relative(0.98, scoll_bar_y, after_sleep=1)
                        self.click_relative(mission.get("entry")[0], mission.get("entry")[1], after_sleep=1)  # Go
                        self.sleep(1)
                        self.click_relative(0.93, 0.90, after_sleep=1)  # Fast Travel
                        self.wait_in_team_and_world(time_out=180)
                        # move to combat zone
                        self.run_until(lambda: False, t.get('direction'), t.get('running_time'), running=True)
                        # collect echo again
                        self.log_info('execute | collect echo again')
                        collected = self.walk_find_echo(time_out=10, backward_time=5)
                    break
            if not tdn_found:
                self.log_warn(f"execute | mission not existent in tdn | mission name = {mission.get("name")} | tdn = {self.tdn}")
        self.ensure_main(time_out=180)
