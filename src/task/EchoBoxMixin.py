import re

from ok import Box, PostMessageInteraction, TaskDisabledException
from ok.device.interaction_methods.pynput import PynputInteraction


class EchoBoxResultUncertain(RuntimeError):
    """确认可能已送达，禁止因识别失败再次使用箱子。"""


class EchoBoxMixin:
    """每日任务的开箱操作，每次最多确认使用一个箱子。"""

    BOX_FEATURES = tuple(f'echo_box_item_{i}' for i in range(1, 8)) + ('echo_box_item_1_selected',)
    SPECIAL_FEATURES = (
        'echo_box_special_normal', 'echo_box_special_hover', 'echo_box_special_selected',
    )
    STEP_TIMEOUT = 10
    # 游戏文字与软件显示语言分开；繁中 OCR 可能被框架转换为简中。
    GAME_TEXT = {
        'zh_CN': {
            'special': r'特殊', 'use': r'使用', 'confirm': r'确认', 'cancel': r'取消',
            'quantity': r'使用数目', 'reward': r'点击空白处继续',
        },
        'zh_TW': {
            'special': r'特殊', 'use': r'使用', 'confirm': r'確認|确认', 'cancel': r'取消',
            'quantity': r'使用數目|使用数目', 'reward': r'點擊空白處繼續|点击空白处继续',
        },
        'en_US': {
            'special': r'Special', 'use': r'Use', 'confirm': r'Confirm', 'cancel': r'Cancel',
            'quantity': r'Quantity(?:\s+to\s+Use)?|Use\s+(?:Amount|Quantity)|Amount',
            'reward': r'(?:Click|Tap)\s+(?:anywhere|(?:the\s+)?blank\s+(?:area|space))'
                      r'\s+to\s+(?:continue|close)|Click\s+to\s+Continue',
        },
    }

    def _echo_box_step(self, text):
        """复用固定状态行，下一步覆盖上一步，不堆积诊断字段。"""
        self.info_set('current task', text)
        self.log_info(text)

    def _echo_box_pattern(self, key):
        return re.compile(r'^\s*(?:' + self.GAME_TEXT[self.game_lang][key] + r')\s*$', re.IGNORECASE)

    def use_one_echo_box(self):
        """成功返回 True，无箱子或不支持的游戏语言返回 False；不确定时抛出异常。

        确认只发送一次。奖励出现后即使数量尚未刷新，也只等待校验，不重复开箱。
        """
        if self.game_lang not in self.GAME_TEXT:
            self.log_info(self.tr('Echo box skipped: unsupported game language.'))
            return False
        self.open_special_inventory()
        self._echo_box_step(self.tr('Looking for an Echo box on the current page'))
        # 只检查当前一屏，不滚动物品列表。
        matches = self.find_visible_boxes()
        if not matches:
            self.sleep(0.5)
            self.next_frame()
            matches = self.find_visible_boxes()
        if not matches:
            self.log_info(self.tr('No Echo boxes found on the current page.'))
            return False

        target = matches[0]
        self.log_debug(f'Echo box template: {target.name}, position: {target.x}, {target.y}')
        self.click_box(target, down_time=0.15, after_sleep=0.5)
        quantity_box = self.quantity_region(target)
        original_name, original_count = self.read_inventory_item(quantity_box)
        self.log_debug(f'Echo box before use: {original_name} ({original_count})')
        self.screenshot('DailyEchoBox_before')

        self.use_box_once(original_count)
        # 等待实际减一，不把连续两帧的旧数量当作本次未消耗的证据。
        self.read_inventory_item(quantity_box, original_name=original_name, original_count=original_count)
        self.screenshot('DailyEchoBox_success')
        self.log_info(self.tr('Used one Echo box and verified its consumption.'))
        return True

    def open_special_inventory(self):
        """定位特殊分类；后台通过按住分类栏滚动，不移动真实鼠标或切换输入后端。"""
        self._echo_box_step(self.tr('Opening the Bag and locating the Special tab'))
        self.send_key(self.key_config.get('Bag Key', 'b'), after_sleep=1)
        sidebar = self.box_of_screen(0.015, 0.10, 0.07, 0.95)

        def locate_special():
            """兼容特殊分类图标的普通、悬停和选中状态，返回匹配位置。"""
            for feature in self.SPECIAL_FEATURES:
                box = self.find_one(feature, box=sidebar, threshold=0.85, use_gray_scale=True)
                if box:
                    return box

        target = self.wait_until(locate_special, time_out=2, settle_time=0)
        if not target:
            anchor = self.wait_feature(
                # 当前未选中资源分类实测灰阶匹配约 0.63；该锚点只用于定位侧栏。
                'echo_box_sidebar_anchor', box=sidebar, threshold=0.6, use_gray_scale=True,
                time_out=self.STEP_TIMEOUT, raise_if_not_found=True,
            )
            anchor_x, anchor_y = anchor.center()
            self._echo_box_step(self.tr('Scrolling the Bag category sidebar'))
            for _ in range(10):
                self._echo_box_scroll_sidebar(anchor_x, anchor_y)
                self.sleep(0.3)
                self.next_frame()
                target = locate_special()
                if target:
                    break
        if not target:
            raise RuntimeError(self.tr('Could not find the Special tab in the Bag.'))
        self.click_box(target, down_time=0.15, after_sleep=0.5)
        self.wait_until(self.is_special_inventory, time_out=self.STEP_TIMEOUT,
                        settle_time=0.3, raise_if_not_found=True)
        return True

    def _echo_box_scroll_sidebar(self, x, y):
        """按住后台分类栏使其接收滚动；普通滚轮会落到真实指针所在的说明区。"""
        self._echo_box_check_scroll_focus()
        self.move(x, y)
        self.sleep(0.2)
        interaction = self.executor.interaction
        if isinstance(interaction, PostMessageInteraction):
            try:
                interaction.mouse_down(x, y)
                self.sleep(0.2)
                self.scroll(x, y, -4)
                self.sleep(0.3)
            finally:
                # 直接释放库的后台按键，确保用户停止或异常时也不会留下按住状态。
                interaction.mouse_up()
        else:
            self._echo_box_check_scroll_focus()
            self.scroll(x, y, -1)

    def _echo_box_check_scroll_focus(self):
        interaction = self.executor.interaction
        if isinstance(interaction, PynputInteraction) and not interaction.clickable():
            raise RuntimeError(self.tr('Keep the game in the foreground while scrolling the Bag categories.'))

    def is_special_inventory(self):
        """通过分类标题确认背包页面，避免在数量或奖励弹窗中校验。"""
        # OCR 会把标题和容量读成同一行，例如「特殊 62/1000」。
        title = re.compile(r'^\s*(?:' + self.GAME_TEXT[self.game_lang]['special'] + r')(?=\s|[0-9]|$)',
                           re.IGNORECASE)
        return bool(self.ocr(0.05, 0.035, 0.22, 0.085, match=title))

    def find_visible_boxes(self):
        """匹配当前屏中的声骸箱子，去重后按从上到下、从左到右的顺序返回。"""
        area = self.box_of_screen(0.085, 0.12, 0.63, 0.855)
        matches = []
        for feature in self.BOX_FEATURES:
            matches.extend(self.find_feature(feature, box=area, threshold=0.88))
        # 相似模板可能匹配同一格，只保留置信度最高的结果。
        unique = []
        for box in sorted(matches, key=lambda b: b.confidence, reverse=True):
            if not any(abs(box.x - other.x) < box.width / 2 and
                       abs(box.y - other.y) < box.height / 2 for other in unique):
                unique.append(box)
        # 匹配位置可能有少量纵向误差，先按物品行分组再按横坐标排序。
        return sorted(unique, key=lambda b: (round(b.y / (self.height * 0.196)), b.x))

    @staticmethod
    def quantity_region(target):
        """根据图标匹配位置和缩放比例，计算原物品格子下方的数量识别区域。"""
        # 基准画面为 2048×1152；图标裁剪为 130×115，
        # 相对 155×190 物品格子的偏移为 (10, 28)，选中态模板也遵循此布局。
        sx, sy = target.width / 130, target.height / 115
        return Box(round(target.x - 5 * sx), round(target.y + 122 * sy),
                   round(150 * sx), round(39 * sy), name='echo_box_quantity')

    @staticmethod
    def clean_text(text):
        """去除 OCR 文本中的空白，避免同一名称因空格或换行被判为不同物品。"""
        return re.sub(r'\s+', '', text)

    def read_inventory_item(self, quantity_box, original_name=None, original_count=None):
        """初始读取要求两帧一致；使用后则等待两帧一致且确实消耗一个。

        原数量为 1 时，以名称稳定变化确认消失，不读取补位物品的数量。
        未变化只继续等待，异常变化立即停止，不再发送开箱操作。
        """
        self._echo_box_step(self.tr('Reading the item name and quantity'))
        previous = None
        repeats = 0

        def read_stable():
            nonlocal previous, repeats
            value = None
            if self.is_special_inventory():
                titles = self.ocr(0.69, 0.10, 0.98, 0.17, threshold=0.8)
                title = ''.join(self.clean_text(b.name) for b in sorted(titles, key=lambda b: (b.y, b.x)))
                if title and any(c.isalpha() for c in title):
                    if original_count == 1 and title != original_name:
                        value = (title, None)
                    else:
                        counts = self.ocr(box=quantity_box, match=re.compile(r'^\s*[0-9]+\s*$'), threshold=0.8)
                        if len(counts) == 1 and re.fullmatch(r'\s*[0-9]+\s*', counts[0].name):
                            count = int(counts[0].name.strip())
                            if count > 0:
                                value = (title, count)
            repeats = repeats + 1 if value is not None and value == previous else 1
            previous = value
            if value is None or repeats < 2:
                return None
            if original_count is not None and not self.verify_consumption(
                    original_name, original_count, *value):
                return None
            return value

        value = self.wait_until(read_stable, time_out=self.STEP_TIMEOUT, settle_time=0)
        if value is None:
            if original_count is not None:
                raise EchoBoxResultUncertain(self.tr(
                    'Echo box result is uncertain. Check the Bag before running again; no retry was sent.'))
            raise RuntimeError(self.tr('Could not reliably read the item name and quantity. No box was used.'))
        self.log_debug(f'Echo box inventory reading: {value}')
        return value

    def click_text(self, key, region):
        """等待唯一游戏按钮；匹配词按游戏语言选取，不按软件语言翻译。"""
        boxes = self.wait_ocr(*region, match=self._echo_box_pattern(key),
                              time_out=self.STEP_TIMEOUT, settle_time=0.2,
                              raise_if_not_found=True)
        if len(boxes) != 1:
            raise RuntimeError(self.tr('Could not uniquely locate an Echo box button.'))
        self.click_box(boxes[0], down_time=0.15, after_sleep=0.3)

    def use_box_once(self, original_count):
        """校验数目为 1 后仅确认一次；确认后任何识别异常都视为待核实。"""
        self._echo_box_step(self.tr('Using one Echo box'))
        self.click_text('use', (0.76, 0.87, 0.98, 0.96))
        quantity_pattern = re.compile(
            r'^\s*(?:' + self.GAME_TEXT[self.game_lang]['quantity'] + r')\s*[:：]\s*1\s*$',
            re.IGNORECASE,
        )
        self.wait_ocr(0.35, 0.53, 0.65, 0.59, match=quantity_pattern,
                      time_out=self.STEP_TIMEOUT, settle_time=0.2, raise_if_not_found=True)
        try:
            self.click_text('confirm', (0.60, 0.69, 0.79, 0.76))
            self.click_text('reward', (0.22, 0.85, 0.78, 0.93))
            if original_count > 1:
                self.click_text('cancel', (0.20, 0.69, 0.40, 0.76))
        except TaskDisabledException:
            raise
        except Exception as error:
            raise EchoBoxResultUncertain(self.tr(
                'Echo box result is uncertain. Check the Bag before running again; no retry was sent.')) from error

    def verify_consumption(self, original_name, original_count, current_name, current_count):
        """未变化返回 False 以继续等刷新；异常结果禁止重试。"""
        if original_count == 1:
            if current_name != original_name:
                return True
            if current_count == 1:
                return False
        elif current_name == original_name:
            if current_count == original_count - 1:
                return True
            if current_count == original_count:
                return False
        raise EchoBoxResultUncertain(self.tr(
            'Echo box result is uncertain. Check the Bag before running again; no retry was sent.'))
