import re

import win32api

from ok import Box, PostMessageInteraction


class EchoBoxMixin:
    """提供每日任务共用的开箱操作；成功使用一个声骸箱子后立即结束。"""

    BOX_FEATURES = tuple(f'echo_box_item_{i}' for i in range(1, 8)) + ('echo_box_item_1_selected',)
    SPECIAL_FEATURES = (
        'echo_box_special_normal', 'echo_box_special_hover', 'echo_box_special_selected',
    )
    EMPTY_MESSAGE = '声骸箱子已用尽，无法通过声骸箱子完成日常任务'
    MAX_ATTEMPTS = 3
    STEP_TIMEOUT = 10

    def step(self, text):
        """同步更新任务状态和日志，便于定位当前执行步骤。"""
        self.info_set('当前步骤', text)
        self.log_info(text)

    def use_one_echo_box(self):
        """选择当前屏的箱子并校验消耗结果，首次失败后最多额外重试两次。

        成功返回 True；当前屏无箱子返回 False；识别异常或重试耗尽则抛出异常，
        由每日任务负责记录错误、恢复页面并继续后续流程。
        """
        self.open_special_inventory()
        self.step('在当前一屏查找声骸箱子')
        # 只检查当前一屏，不滚动物品列表。
        matches = self.find_visible_boxes()
        if not matches:
            self.sleep(0.5)
            self.next_frame()
            matches = self.find_visible_boxes()
        if not matches:
            self.log_info(self.EMPTY_MESSAGE, notify=True)
            return False

        target = matches[0]
        self.info_set('箱子模板', target.name)
        self.info_set('箱子位置', f'{target.x}, {target.y}')
        self.click_box(target, after_sleep=0.5)
        quantity_box = self.quantity_region(target)
        original_name, original_count = self.read_inventory_item(quantity_box)
        self.info_set('选中物品', original_name)
        self.info_set('初始数量', original_count)
        self.log_info(f'选中声骸箱子：{original_name}，数量：{original_count}')
        self.screenshot('DailyEchoBox_before')

        for attempt in range(self.MAX_ATTEMPTS):
            self.info_set('重试次数', attempt)
            self.use_box_once(original_count)
            # 最后一个箱子用完后，游戏会自动选中其他物品，以名称变化判定成功。
            current_name, current_count = self.read_inventory_item(
                quantity_box, original_name=original_name, original_count=original_count,
            )
            self.info_set('校验物品', current_name)
            self.info_set('校验数量', current_count if current_count is not None else '原物品已消失')
            self.log_info(f'校验声骸箱子：{original_name}({original_count}) → '
                          f'{current_name}({current_count})')
            if self.verify_consumption(original_name, original_count, current_name, current_count):
                self.screenshot('DailyEchoBox_success')
                return True
            if attempt + 1 < self.MAX_ATTEMPTS:
                self.log_info(f'声骸箱子数量未变化，开始第{attempt + 1}次重试')
        raise RuntimeError('声骸箱子使用失败：首次执行及2次重试后数量仍未变化')

    def open_special_inventory(self):
        """按配置的背包键进入背包，最多滚动分类栏十次，定位并打开“特殊”页。"""
        self.step('打开背包并寻找特殊分类')
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
                'echo_box_sidebar_anchor', box=sidebar, threshold=0.8, use_gray_scale=True,
                time_out=self.STEP_TIMEOUT, raise_if_not_found=True,
            )
            anchor_x, anchor_y = anchor.center()
            self.step('移动鼠标到左侧分类图标后向下滚动')
            for _ in range(10):
                self.hover_sidebar(anchor_x, anchor_y)
                self.scroll(anchor_x, anchor_y, -1)
                self.sleep(0.3)
                self.next_frame()
                target = locate_special()
                if target:
                    break
        if not target:
            raise RuntimeError('滚动10次后仍未找到背包特殊分类')
        self.click_box(target, after_sleep=0.5)
        self.wait_until(self.is_special_inventory, time_out=self.STEP_TIMEOUT,
                        settle_time=0.3, raise_if_not_found=True)

    def hover_sidebar(self, x, y):
        """将鼠标移至分类图标中心，短暂停留并确认真实位置后才允许滚动。

        x、y 是游戏画面坐标；后台输入模式还需转换成桌面坐标移动真实指针。
        """
        # PostMessage.move 只发送移动消息，背包滚轮还要求真实指针停在分类栏。
        self.move(x, y)
        interaction = self.executor.interaction
        if isinstance(interaction, PostMessageInteraction):
            screen_pos = interaction.capture.get_abs_cords(x, y)
            win32api.SetCursorPos(screen_pos)
            self.sleep(0.2)
            actual = win32api.GetCursorPos()
            self.info_set('分类栏鼠标位置', f'目标 {screen_pos}，实际 {actual}')
            if max(abs(actual[i] - screen_pos[i]) for i in (0, 1)) > 3:
                raise RuntimeError('鼠标未停在左侧分类图标上，停止滚动')
        else:
            self.sleep(0.2)

    def is_special_inventory(self):
        """通过清晰的“特殊”页标题确认已回到背包，避免在数量或奖励弹窗中校验。"""
        return bool(self.ocr(0.05, 0.035, 0.18, 0.085, match=re.compile(r'^特殊')))

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
        """根据图标匹配位置和缩放比例，计算该物品格子下方的数量识别区域。"""
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
        """连续两帧读取一致后返回物品名称和数量，超时则抛出识别异常。

        初始数量为 1 且名称已变化时，返回 (新名称, None)，无需读取补位物品数量。
        其他情况从 quantity_box 指定的原格子数量区域读取正整数。
        """
        self.step('识别并校验物品名称和数量')
        previous = None
        repeats = 0

        def read_stable():
            """确认背包页面并读取一帧数据；结果连续一致时才交给外层校验。"""
            nonlocal previous, repeats
            value = None
            if self.is_special_inventory():
                titles = self.ocr(0.69, 0.10, 0.98, 0.17, threshold=0.8)
                title = ''.join(self.clean_text(b.name) for b in sorted(titles, key=lambda b: (b.y, b.x)))
                if title and re.search(r'[\u4e00-\u9fff]', title):
                    if original_count == 1 and title != original_name:
                        value = (title, None)
                    else:
                        counts = self.ocr(box=quantity_box, match=re.compile(r'^\s*[0-9]+\s*$'), threshold=0.8)
                        if len(counts) == 1:
                            count = int(counts[0].name.strip())
                            if count > 0:
                                value = (title, count)
            repeats = repeats + 1 if value is not None and value == previous else 1
            previous = value
            return value if value is not None and repeats >= 2 else None

        value = self.wait_until(read_stable, time_out=self.STEP_TIMEOUT, settle_time=0)
        if value is None:
            raise RuntimeError('无法可靠识别背包页面、物品名称或数量，停止开箱')
        return value

    def click_text(self, label, region):
        """在归一化坐标区域 region 内等待唯一的按钮文字，定位后移动并点击。"""
        self.step(f'查找并点击“{label}”')
        boxes = self.wait_ocr(*region, match=re.compile(r'^\s*' + re.escape(label) + r'\s*$'),
                              time_out=self.STEP_TIMEOUT, settle_time=0.2,
                              raise_if_not_found=True)
        if len(boxes) != 1:
            raise RuntimeError(f'无法唯一定位按钮：{label}')
        self.click_box(boxes[0], after_sleep=0.3)

    def use_box_once(self, original_count):
        """执行一次使用、确认和关闭奖励弹窗的操作，确认使用数目固定为 1。

        初始数量大于 1 时还需点击“取消”；初始数量为 1 时直接进入结果校验。
        """
        self.click_text('使用', (0.76, 0.87, 0.98, 0.96))
        self.step('确认本次使用数目为1')
        self.wait_ocr(0.44, 0.53, 0.57, 0.59,
                      match=re.compile(r'^\s*使用数目\s*[:：]\s*1\s*$'),
                      time_out=self.STEP_TIMEOUT, settle_time=0.2, raise_if_not_found=True)
        self.click_text('确认', (0.60, 0.69, 0.79, 0.76))
        self.click_text('点击空白处继续', (0.42, 0.85, 0.59, 0.93))
        if original_count > 1:
            self.click_text('取消', (0.20, 0.69, 0.40, 0.76))

    @staticmethod
    def verify_consumption(original_name, original_count, current_name, current_count):
        """按初始数量判断是否成功：多数量要求同名且减一，单数量要求名称改变。

        明确未消耗时返回 False 以允许重试；其他不确定结果抛出异常，避免重复消耗。
        """
        if original_count == 1:
            if current_name != original_name:
                return True
            if current_count == 1:
                return False
        else:
            if current_name == original_name:
                if current_count == original_count - 1:
                    return True
                if current_count == original_count:
                    return False
        raise RuntimeError('开箱校验结果不确定，停止重试，避免重复消耗箱子')
