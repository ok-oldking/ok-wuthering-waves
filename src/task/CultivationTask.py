import re
import time
import unicodedata
from dataclasses import dataclass

from ok import CannotFindException, TaskDisabledException, WaitFailedException
from src.task.BaseCombatTask import NotInCombatException
from src.task.DomainTask import DomainTask
from src.task.task_icons import task_icon


def compact_text(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def parse_quantity(text):
    match = re.fullmatch(r'(\d{1,7})/(\d{1,7})', compact_text(text))
    if match is None or int(match[2]) == 0:
        return None
    return int(match[1]), int(match[2])


@dataclass
class MaterialGoal:
    name: str
    owned: int
    required: int
    material_type: str = ''
    weekly_left: int | None = None

    @property
    def missing(self):
        return max(0, self.required - self.owned)


@dataclass
class MaterialRow:
    material_type: str
    y: float
    quantities: list
    weekly_left: int | None = None


class CultivationError(RuntimeError):
    pass


class CultivationTask(DomainTask):
    MATERIALS = ('共鸣者突破材料', '技能升级材料')
    MATERIAL_OPTIONS = {
        '共鸣者突破材料': 'Ascension Materials',
        '技能升级材料': 'Skill Materials',
    }
    WEEKLY_MATERIAL = '技能升级材料'
    WEEKLY_PATTERN = re.compile(r'本周剩余可收取次数[:：]?(\d+)/\d+')
    CLAIM_COST_PATTERN = re.compile(r'领取奖励需消耗\s*(\d+)\s*点结晶波片')
    CHALLENGE_BUTTON_X = 0.900
    CHALLENGE_BUTTON_Y = {
        '共鸣者突破材料': 0.320,
        '技能升级材料': 0.597,
    }
    SOLO_CHALLENGE = (0.800, 0.910)
    REWARD_SLOT_Y = 0.526
    REWARD_SLOT_SPACING = 0.0878
    REWARD_SLOT_INDEX = 4
    COST = 60
    READ_ATTEMPTS = 3
    COMBAT_TIMEOUT = 600

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Cultivation Resource Farm'
        self.description = ('Farm Ascension and Skill Materials for the selected Guidebook cultivation target. '
                            'Skill Materials allow 3 reward claims per week. '
                            'Simplified Chinese, 16:9. Uses current Waveplates only.')
        self.icon = task_icon('forgery')
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.supported_languages = ['zh_CN']
        self.default_config = {
            'Ascension Materials': True,
            'Skill Materials': True,
        }
        self._combat_deadline = 0
        self.goals = []

    def enabled_materials(self):
        return [material_type for material_type in self.MATERIALS
                if self.config.get(self.MATERIAL_OPTIONS[material_type], True)]

    def material_label(self, material_type):
        return self.tr(self.MATERIAL_OPTIONS[material_type])

    def sleep_check(self):
        if self._combat_deadline and time.monotonic() >= self._combat_deadline:
            raise CultivationError(
                self.tr('Combat exceeded {seconds} seconds. Stopped. Check the team and retry.').format(
                    seconds=self.COMBAT_TIMEOUT))
        super().sleep_check()

    def read_stable(self, reader, label):
        previous = None
        for _ in range(self.READ_ATTEMPTS):
            self.next_frame()
            value = reader()
            if value is not None and value == previous:
                return value
            previous = value
            self.sleep(0.3)
        raise CultivationError(
            self.tr('Failed to read {label}. Stopped. Check the game screen and retry.').format(label=label))

    def open_cultivation(self):
        self.openF2Book('gray_book_boss')
        self.click(0.24, 0.17, after_sleep=1)
        if not self.wait_until(self.is_cultivation_page, time_out=5):
            raise CultivationError(
                self.tr('Cultivation target page did not open. Select a cultivation target in the Guidebook.'))

    def is_cultivation_page(self):
        texts = {compact_text(b.name) for b in self.ocr(0.1, 0.12, 0.6, 0.2)}
        return {'培养目标', '所需材料'} <= texts

    def read_current_stamina(self):
        def read():
            current, _, _ = self.get_stamina()
            return current if current >= 0 else None

        stamina = self.read_stable(read, self.tr('Current Waveplates'))
        self.info_set('current_stamina', stamina)
        return stamina

    def read_remaining_stamina(self):
        def read():
            values = []
            for box in self.ocr(0.48, 0.87, 0.75, 0.97):
                if match := re.fullmatch(r'剩余(\d{1,7})', compact_text(box.name)):
                    values.append(int(match[1]))
            return values[0] if len(values) == 1 else None

        stamina = self.read_stable(read, self.tr('Remaining Waveplates on the result screen'))
        self.info_set('current_stamina', stamina)
        return stamina

    def read_target_row(self, material_type):
        labels = [b for b in self.ocr(0.36, 0.18, 0.64, 0.75)
                  if compact_text(b.name) == material_type]
        if len(labels) != 1:
            return None
        y = labels[0].center()[1] / self.height
        quantities = []
        weekly_left = None
        for box in self.ocr(0.36, y + 0.01, 0.82, y + 0.075):
            text = compact_text(box.name)
            if (value := parse_quantity(text)) is not None:
                quantities.append((box, value))
            elif weekly_left is None and material_type == self.WEEKLY_MATERIAL:
                if match := self.WEEKLY_PATTERN.search(text):
                    weekly_left = int(match[1])
        quantities.sort(key=lambda entry: entry[0].x)
        if not quantities:
            return None
        return MaterialRow(material_type, y, quantities, weekly_left)

    def read_item_detail(self, material_types):
        if isinstance(material_types, str):
            material_types = (material_types,)
        boxes = self.ocr(0.2, 0.08, 0.8, 0.9)
        kinds = [b for b in boxes if compact_text(b.name) in material_types]
        if len(kinds) != 1:
            return None
        kind = kinds[0]
        titles = [b for b in boxes if 0 < kind.y - b.y < self.height * 0.10
                  and abs(b.x - kind.x) < self.width * 0.04]
        owned = []
        for box in boxes:
            if match := re.fullmatch(r'拥有[:：]?(\d{1,7})', compact_text(box.name)):
                owned.append(int(match[1]))
        if not titles or len(owned) != 1:
            return None
        title = max(titles, key=lambda b: b.y)
        return compact_text(title.name), owned[0]

    def close_item_detail(self):
        self.click(0.5, 0.94, after_sleep=0.3)

    def read_goals(self):
        rows = []
        for material_type in self.enabled_materials():
            def read_row(material_type=material_type):
                row = self.read_target_row(material_type)
                if row is None:
                    return None
                return (tuple(v for _, v in row.quantities), row.weekly_left)

            expected = self.read_stable(
                read_row, self.tr('{material} quantities').format(material=self.material_label(material_type)))
            row = self.read_target_row(material_type)
            if row is None or (tuple(v for _, v in row.quantities), row.weekly_left) != expected:
                raise CultivationError(
                    self.tr('{material} quantities changed. Stopped. Run the task again.').format(
                        material=self.material_label(material_type)))
            if material_type == self.WEEKLY_MATERIAL and row.weekly_left is None:
                raise CultivationError(
                    self.tr('Weekly claims left for Skill Materials not recognized. Stopped. Check the cultivation target.'))
            rows.append(row)

        goals = []
        for row in rows:
            for box, (owned, required) in row.quantities:
                self.click(box, after_sleep=0.4)
                try:
                    name, actual = self.read_stable(
                        lambda: self.read_item_detail((row.material_type,)), self.tr('Material details'))
                finally:
                    self.close_item_detail()
                if actual != owned or any(g.name == name for g in goals):
                    raise CultivationError(
                        self.tr('Material inventory does not match the cultivation page. Stopped. Check the cultivation target.'))
                goals.append(MaterialGoal(name, actual, required,
                                          row.material_type, row.weekly_left))
        self.report_goals(goals)
        return goals

    def report_goals(self, goals):
        for goal in goals:
            state = self.tr('Met') if goal.missing == 0 else self.tr('{count} missing').format(count=goal.missing)
            if goal.weekly_left is not None:
                state += self.tr(', {count} weekly claims left').format(count=goal.weekly_left)
            self.info_set(goal.name, self.tr('{owned}/{required}, {state}').format(
                owned=goal.owned, required=goal.required, state=state))
            self.log_info(self.tr('Material: {name}, owned {owned}, required {required}, {state}').format(
                name=goal.name, owned=goal.owned, required=goal.required, state=state))

    def weekly_left(self, material_type):
        if material_type != self.WEEKLY_MATERIAL:
            return None
        values = [g.weekly_left for g in self.goals
                  if g.material_type == material_type and g.weekly_left is not None]
        return min(values) if values else 0

    def consume_weekly(self, material_type):
        if material_type != self.WEEKLY_MATERIAL:
            return
        for goal in self.goals:
            if goal.material_type == material_type and goal.weekly_left is not None:
                goal.weekly_left -= 1

    def enter_challenge(self, material_type):
        if self.read_target_row(material_type) is None:
            raise CultivationError(
                self.tr('{material} row is missing. Stopped. Check the cultivation target.').format(
                    material=self.material_label(material_type)))
        # 培养页行位置固定，直接使用比例坐标点击，按钮文字随版本变化也不影响。
        self.click(self.CHALLENGE_BUTTON_X, self.CHALLENGE_BUTTON_Y[material_type], after_sleep=1)
        if not self.wait_feature('team_start_challenge', time_out=10, raise_if_not_found=False):
            # 技能材料行先打开副本详情页，需要再点单人挑战。
            self.click(*self.SOLO_CHALLENGE, after_sleep=1)
            if not self.wait_feature('team_start_challenge', time_out=20, raise_if_not_found=False):
                raise CultivationError(self.tr('Team page did not open. Stopped. Check the selected challenge.'))
        self.click_team_challenge()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def fight(self):
        self._combat_deadline = time.monotonic() + self.COMBAT_TIMEOUT
        try:
            self.combat_once(wait_combat_time=30, target=True)
        finally:
            self._combat_deadline = 0
            self.reset_combat_state('cultivation combat ended')

    def collect_optional_echo(self):
        try:
            if self.pick_echo():
                return
            # 残像聚落的找声骸方法：先向前找，再转向扫描。
            if self.walk_find_echo(time_out=5, backward_time=2.5):
                return
            self.yolo_find_echo(turn=True, use_color=False, time_out=30)
        except TaskDisabledException:
            raise
        except Exception as error:
            self.log_warning(
                self.tr('Echo pickup incomplete, continuing to claim materials: {error}').format(error=error))
        finally:
            for key in ('w', 'a', 's', 'd'):
                self.send_key_up(key)

    def result_buttons(self):
        buttons = {compact_text(b.name): b for b in self.ocr(0.25, 0.78, 0.76, 0.90)}
        if '退出副本' in buttons and '重新挑战' in buttons:
            return buttons
        return None

    def read_claim_cost(self):
        for box in self.ocr(0.25, 0.4, 0.75, 0.55, match=self.CLAIM_COST_PATTERN):
            if match := self.CLAIM_COST_PATTERN.search(box.name):
                return int(match[1])
        return None

    def has_claim_stamina(self):
        # 部分培养目标副本的领奖弹窗没有 claim_stamina_sign，改认弹窗文字。
        return not self.in_team()[0] and (self.find_one('claim_stamina_sign') or
                                          self.read_claim_cost() is not None)

    def confirm_single_claim(self):
        self.sleep(1)
        claim_cost = self.read_claim_cost()
        if claim_cost is None:
            # 带双倍选项的弹窗，左键为单倍领取。
            self.click_dialog_left_button()
        elif claim_cost == self.COST:
            self.click_dialog_right_button()
        else:
            raise CultivationError(
                self.tr('Claim costs {cost} Waveplates, expected {expected}. Stopped.').format(
                    cost=claim_cost, expected=self.COST))

    def claim_reward(self):
        for _ in range(2):
            if self.has_claim_stamina():
                break
            try:
                self.walk_to_treasure()
            except WaitFailedException as error:
                raise CultivationError(
                    self.tr('Reward chest not found. Stopped. Make sure the battle has ended.')) from error
            self.pick_f(handle_claim=False)
            if self.wait_until(self.has_claim_stamina, time_out=3):
                break
        if not self.has_claim_stamina():
            raise CultivationError(self.tr('Claim dialog did not open. Stopped. Check the reward chest.'))
        before = self.read_current_stamina()
        if before < self.COST:
            self.send_key('esc', after_sleep=0.5)
            raise CultivationError(self.tr('Waveplates below {cost}. Claim cancelled.').format(cost=self.COST))
        self.confirm_single_claim()
        # 确认后只等待领取结果，避免延迟到账时重复扣费。
        if not self.wait_until(self.result_buttons, time_out=15):
            raise CultivationError(
                self.tr('Claim result not confirmed. Stopped. Check the rewards before running again.'))
        return before

    def read_reward_inventory(self, material_type):
        names = {g.name for g in self.goals if g.material_type == material_type}
        if len(names) != 1:
            raise CultivationError(
                self.tr('Unexpected cultivation material count. Stopped. Check the cultivation target.'))
        boxes = self.ocr(0.12, 0.40, 0.89, 0.68)
        slots = [b for b in boxes if re.fullmatch(r'[xX×]\d{1,7}', compact_text(b.name))]
        if not 1 <= len(slots) <= 12:
            raise CultivationError(self.tr('Rewards not recognized. Stopped. Check the reward screen.'))
        # 目标材料固定在结算行第 5 格，只点这一格读取库存。
        slot_x = 0.5 + (self.REWARD_SLOT_INDEX - (len(slots) - 1) / 2) * self.REWARD_SLOT_SPACING
        self.click(slot_x, self.REWARD_SLOT_Y, name='奖励槽5', after_sleep=0.4)
        try:
            name, owned = self.read_stable(
                lambda: self.read_item_detail(self.MATERIALS), self.tr('Reward material inventory'))
        finally:
            self.close_item_detail()
        if name not in names:
            raise CultivationError(
                self.tr('Reward slot 5 is {name}, not a target material. Stopped. Check the rewards.').format(
                    name=name))
        return {name: owned}

    def update_goals(self, inventory):
        if not set(inventory) <= {g.name for g in self.goals}:
            raise CultivationError(self.tr('Unknown material in the reward inventory. Stopped. Check the rewards.'))
        if any(inventory[g.name] < g.owned for g in self.goals if g.name in inventory):
            raise CultivationError(
                self.tr('Reward inventory is lower than before the claim. Stopped. Check the materials.'))
        if not any(inventory[g.name] > g.owned for g in self.goals
                   if g.name in inventory and g.missing):
            raise CultivationError(
                self.tr('Target materials did not increase after the claim. Stopped. Check the rewards.'))
        for goal in self.goals:
            if goal.name in inventory:
                goal.owned = inventory[goal.name]
        self.report_goals(self.goals)

    def restart_challenge(self):
        buttons = self.result_buttons()
        if buttons is None:
            raise CultivationError(self.tr('Result screen closed before restarting. Stopped.'))
        self.click(buttons['重新挑战'], after_sleep=1)
        self.wait_click_skip_dialog_confirm()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def leave_challenge(self):
        if buttons := self.result_buttons():
            self.click(buttons['退出副本'], after_sleep=1)
            if not self.wait_until(self.in_world, time_out=self.teleport_timeout):
                raise CultivationError(self.tr('Leaving the challenge timed out. Return to the open world manually.'))
        else:
            self.make_sure_in_world()

    def farm(self, stamina):
        # 上限只限制消耗；完成状态始终以领取后的实际库存为准。
        max_claims = stamina // self.COST
        pending = []
        for material_type in self.MATERIALS:
            goals = [g for g in self.goals if g.material_type == material_type]
            if not goals or all(g.missing == 0 for g in goals):
                continue
            if self.weekly_left(material_type) == 0:
                self.log_info(self.tr('{material} has 0 weekly claims left, skipped').format(
                    material=self.material_label(material_type)))
                continue
            pending.append(material_type)
        if not pending:
            if all(g.missing == 0 for g in self.goals):
                self.info_set(self.tr('Stop Reason'), self.tr('Cultivation materials meet the target'))
            else:
                self.info_set(self.tr('Stop Reason'), self.tr('Skill Materials have 0 weekly claims left'))
            return
        weekly_exhausted = False
        for index, material_type in enumerate(pending):
            if max_claims <= 0:
                self.info_set(self.tr('Stop Reason'), self.tr('Waveplate budget from the task start is used up'))
                return
            self.enter_challenge(material_type)
            while True:
                for attempt in range(2):
                    try:
                        self.fight()
                        break
                    except (NotInCombatException, CannotFindException, WaitFailedException) as error:
                        self.log_warning(self.tr('Challenge not completed, attempt {attempt}: {error}').format(
                            attempt=attempt + 1, error=error))
                        if attempt == 1:
                            raise CultivationError(
                                self.tr('Challenge failed 2 times in a row. Stopped. Check the team.')) from error
                        self.make_sure_in_world()
                        self.open_cultivation()
                        current = self.read_goals()
                        if [(g.name, g.required, g.owned, g.material_type, g.weekly_left)
                            for g in current] != [
                                (g.name, g.required, g.owned, g.material_type, g.weekly_left)
                                for g in self.goals]:
                            raise CultivationError(
                                self.tr('Cultivation target or inventory changed after a failed challenge. Stopped.'))
                        self.goals = current
                        if self.read_current_stamina() < self.COST:
                            self.info_set(self.tr('Stop Reason'), self.tr('Waveplates below {cost}').format(cost=self.COST))
                            return
                        self.enter_challenge(material_type)
                self.collect_optional_echo()
                before = self.claim_reward()
                inventory = self.read_reward_inventory(material_type)
                remaining = self.read_remaining_stamina()
                if remaining > before - self.COST + 1:
                    raise CultivationError(
                        self.tr('Remaining Waveplates after the claim not confirmed. Stopped. Check the rewards.'))
                self.consume_weekly(material_type)
                self.update_goals(inventory)
                self.info_incr('used stamina', self.COST)
                max_claims -= 1
                if all(g.missing == 0 for g in self.goals
                       if g.material_type == material_type):
                    if all(g.missing == 0 for g in self.goals):
                        self.info_set(self.tr('Stop Reason'), self.tr('Cultivation materials meet the target'))
                        return
                    break
                if remaining < self.COST:
                    self.info_set(self.tr('Stop Reason'), self.tr('Waveplates below {cost}').format(cost=self.COST))
                    return
                if max_claims <= 0:
                    self.info_set(self.tr('Stop Reason'), self.tr('Waveplate budget from the task start is used up'))
                    return
                if self.weekly_left(material_type) == 0:
                    weekly_exhausted = True
                    self.log_info(self.tr('{material} weekly claims used up, row finished').format(
                        material=self.material_label(material_type)))
                    break
                self.restart_challenge()
            if index + 1 < len(pending):
                self.leave_challenge()
                self.open_cultivation()
        if weekly_exhausted and any(g.missing for g in self.goals):
            self.info_set(self.tr('Stop Reason'), self.tr('Skill Materials have 0 weekly claims left'))

    def run(self):
        self._combat_deadline = 0
        self.goals = []
        self.info_set('used stamina', 0)
        super().run()
        try:
            if self.game_lang != 'zh_CN' or abs(self.width / self.height - 16 / 9) > 0.01:
                raise CultivationError(
                    self.tr('This task supports Simplified Chinese and 16:9 only. Adjust and retry.'))
            self.make_sure_in_world()
            if not self.enabled_materials():
                self.info_set(self.tr('Stop Reason'), self.tr('No material row enabled'))
                return
            self.open_cultivation()
            self.goals = self.read_goals()
            stamina = self.read_current_stamina()
            if all(g.missing == 0 for g in self.goals):
                self.info_set(self.tr('Stop Reason'), self.tr('Cultivation materials meet the target'))
                self.back(after_sleep=0.5)
                return
            if stamina < self.COST:
                self.info_set(self.tr('Stop Reason'), self.tr('Waveplates below {cost}').format(cost=self.COST))
                self.back(after_sleep=0.5)
                return
            self.farm(stamina)
            self.leave_challenge()
        except TaskDisabledException:
            raise
        except Exception as error:
            self._combat_deadline = 0
            self.reset_combat_state('cultivation failed')
            self.info_set(self.tr('Stop Reason'), str(error))
            self.screenshot('cultivation_failed')
            try:
                self.leave_challenge()
            except TaskDisabledException:
                raise
            except Exception as exit_error:
                self.log_warning(self.tr('Failed to return to the open world. Exit manually: {error}').format(
                    error=exit_error))
            raise
        finally:
            self._combat_deadline = 0
