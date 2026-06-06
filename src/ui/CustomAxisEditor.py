from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import TypeAlias

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

CHARACTER_OPTIONS = [
    ("爱弥斯 / Aemeath", "Aemeath"),
    ("奥古斯塔 / Augusta", "Augusta"),
    ("白芷 / Baizhi", "Baizhi"),
    ("布兰特 / Brant", "Brant"),
    ("卡卡罗 / Calcharo", "Calcharo"),
    ("椿 / Camellya", "Camellya"),
    ("坎特蕾拉 / Cantarella", "Cantarella"),
    ("珂莱塔 / Carlotta", "Carlotta"),
    ("卡提希娅 / Cartethyia", "Cartethyia"),
    ("长离 / Changli", "Changli"),
    ("千咲 / Chisa", "Chisa"),
    ("炽霞 / Chixia", "Chixia"),
    ("夏空 / Ciaccona", "Ciaccona"),
    ("丹瑾 / Danjin", "Danjin"),
    ("达尼亚 / Denia", "Denia"),
    ("卜灵 / Douling", "Douling"),
    ("安可 / Encore", "Encore"),
    ("嘉贝莉娜 / Galbrena", "Galbrena"),
    ("暗主 / HavocRover", "HavocRover"),
    ("光主 / SpectroRover", "SpectroRover"),
    ("风主 / AeroRover", "AeroRover"),
    ("釉瑚 / Hiyuki", "Hiyuki"),
    ("尤诺 / Iuno", "Iuno"),
    ("鉴心 / Jianxin", "Jianxin"),
    ("今汐 / Jinhsi", "Jinhsi"),
    ("忌炎 / Jiyan", "Jiyan"),
    ("琳奈 / Linnai", "Linnai"),
    ("露帕 / Lupa", "Lupa"),
    ("洛可可 / Roccia", "Roccia"),
    ("散华 / Sanhua", "Sanhua"),
    ("守岸人 / ShoreKeeper", "ShoreKeeper"),
    ("桃祈 / Taoqi", "Taoqi"),
    ("维里奈 / Verina", "Verina"),
    ("相里要 / Xiangliyao", "Xiangliyao"),
    ("吟霖 / Yinlin", "Yinlin"),
    ("渊武 / Yuanwu", "Yuanwu"),
    ("赞妮 / Zani", "Zani"),
    ("折枝 / Zhezhi", "Zhezhi"),
    ("Luhesi", "Luhesi"),
    ("Mortefi", "Mortefi"),
    ("Mornye", "Mornye"),
    ("Phoebe", "Phoebe"),
    ("Phrolova", "Phrolova"),
    ("Qiuyuan", "Qiuyuan"),
    ("Xigelika", "Xigelika"),
    ("Youhu", "Youhu"),
]

CHARACTER_DISPLAY_BY_KEY = {key: display for display, key in CHARACTER_OPTIONS}
DEFAULT_TEAM_KEYS = ["Aemeath", "Denia", "Chisa"]
TypingList: TypeAlias = list

ACTION_LABELS = {
    "R": "r",
    "E": "e",
    "E动画": "e_anim",
    "E等待": "e_wait",
    "F一次": "f",
    "F持续检测": "f_until",
    "Q": "q",
    "A": "attack",
    "等待": "wait",
    "重击": "heavy",
    "角色流程": "role_flow",
    "起跳": "jump",
    "闪避": "dodge",
}
FALLBACK_ACTION_LABELS = {
    "平A到协奏满": "attack_until_con",
    "平A到条件满足": "attack_until_condition",
    "重击到条件满足": "heavy_until_condition",
    "重击到协奏满": "heavy_until_con",
    "等待": "wait",
    "重击": "heavy",
    "起跳": "jump",
    "闪避": "dodge",
    "R": "r",
    "E": "e",
    "E动画": "e_anim",
    "E等待": "e_wait",
    "F一次": "f",
    "F持续检测": "f_until",
    "Q": "q",
}
ACTION_DISPLAY_LABELS = {
    "e": "E 共鸣",
    "e_anim": "E 动画等待",
    "r": "R 大招",
    "q": "Q 声骸",
    "attack": "普攻",
    "attack_until_condition": "普攻到条件满足",
    "attack_until_con": "普攻到协奏满",
    "heavy_until_condition": "重击到条件满足",
    "heavy_until_con": "重击到协奏满",
    "heavy": "重击",
    "role_flow": "角色流程",
    "jump": "跳起",
    "dodge": "闪避",
    "wait": "等待",
    "f": "F 交互",
    "f_until": "F 持续检测",
}
TIMED_ACTION_NAMES = {
    'attack', 'attack_until_condition', 'attack_until_con', 'heavy_until_condition', 'heavy_until_con',
    'heavy', 'wait', 'jump', 'dodge', 'f_until',
}
DEFAULT_ACTION_DURATIONS = {
    'attack_until_condition': 3.0,
    'attack_until_con': 3.0,
    'heavy_until_condition': 3.0,
    'heavy_until_con': 3.0,
    'dodge': 0.05,
    'f_until': 1.2,
}
DEFAULT_CONDITIONS = [
    "",
    "1.协奏满==1",
    "1.大招==1",
    "1.技能==1",
    "1.声骸==1",
    "1.buff<=2",
    "2.协奏满==1",
    "2.大招==1",
    "2.技能==1",
    "2.声骸==1",
    "2.buff<=2",
    "3.协奏满==1",
    "3.大招==1",
    "3.技能==1",
    "3.声骸==1",
    "3.buff<=2",
]
AXIS_PHASES = [
    ("startup", "启动轴"),
    ("loop", "循环轴"),
]


def role_display(role_key: str) -> str:
    display = CHARACTER_DISPLAY_BY_KEY.get(role_key, role_key)
    return display.split(" / ", 1)[0]


def default_profile_name(team_keys: TypingList[str]) -> str:
    return " / ".join(role_display(key) for key in team_keys) or "未命名轴"


def action_display(action: "AxisAction") -> str:
    label = ACTION_DISPLAY_LABELS.get(action.name, action.name)
    if action.value is None:
        return label
    value_text = str(int(action.value)) if float(action.value).is_integer() else f"{action.value:.2f}".rstrip('0').rstrip('.')
    return f"{label}: {value_text} 秒"


@dataclass
class AxisAction:
    name: str
    value: float | None = None

    def to_script(self) -> str:
        if self.value is None:
            return self.name
        value_text = str(int(self.value)) if float(self.value).is_integer() else f"{self.value:.2f}".rstrip('0').rstrip('.')
        return f"{self.name}:{value_text}"

    @staticmethod
    def from_raw(raw):
        if isinstance(raw, AxisAction):
            return raw
        if isinstance(raw, str):
            if ':' in raw:
                name, value = raw.split(':', 1)
                try:
                    return AxisAction(name.strip(), float(value))
                except ValueError:
                    return AxisAction(name.strip())
            return AxisAction(raw.strip())
        if isinstance(raw, dict):
            name = raw.get('name') or raw.get('action') or ''
            value = raw.get('value')
            try:
                value = float(value) if value is not None and value != '' else None
            except (TypeError, ValueError):
                value = None
            return AxisAction(str(name).strip(), value)
        return AxisAction(str(raw).strip())


def strip_condition_prefix(condition: str) -> str:
    condition = condition.strip()
    lowered = condition.lower()
    if lowered.startswith('when '):
        return condition[5:].strip()
    for prefix in ('条件', '当', '满足'):
        if condition.startswith(prefix):
            return condition[len(prefix):].lstrip(' :：').strip()
    return condition


def strip_fallback_prefix(text: str) -> str:
    text = text.strip()
    lowered = text.lower()
    if lowered.startswith('fallback '):
        return text[9:].strip()
    for prefix in ('未满足', '否则', '不满足', '条件未满足'):
        if text.startswith(prefix):
            return text[len(prefix):].lstrip(' :：').strip()
    return text


def parse_actions_text(actions_text: str) -> TypingList[AxisAction]:
    return [AxisAction.from_raw(part.strip()) for part in actions_text.replace('，', ',').split(',') if part.strip()]


def parse_fallback_text(text: str) -> tuple[str, TypingList[AxisAction]]:
    text = strip_fallback_prefix(text)
    if ':' in text:
        role, actions_text = text.split(':', 1)
        if role.strip().lower() in ACTION_DISPLAY_LABELS:
            return "", parse_actions_text(text)
        return role.strip(), parse_actions_text(actions_text)
    return "", parse_actions_text(text)


@dataclass
class AxisStep:
    role: str
    actions: TypingList[AxisAction]
    condition: str = ""
    fallback_actions: TypingList[AxisAction] | None = None
    fallback_role: str = ""

    def to_script(self) -> str:
        actions = ", ".join(action.to_script() for action in self.actions)
        line = f"{self.role}: {actions}"
        if self.condition.strip():
            line += f" | 条件 {self.condition.strip()}"
        if self.fallback_actions:
            fallback = ", ".join(action.to_script() for action in self.fallback_actions)
            fallback_role = self.fallback_role.strip() or self.role
            line += f" | 未满足 {fallback_role}: {fallback}"
        return line

    @staticmethod
    def from_raw(raw):
        if isinstance(raw, AxisStep):
            return raw
        if isinstance(raw, str):
            line = raw.strip()
            condition = ""
            fallback_actions = []
            fallback_role = ""
            if '|' in line:
                chunks = [chunk.strip() for chunk in line.split('|')]
                line = chunks[0]
                for chunk in chunks[1:]:
                    if chunk.startswith(('未满足', '否则', '不满足', '条件未满足')) or chunk.lower().startswith('fallback '):
                        fallback_role, fallback_actions = parse_fallback_text(chunk)
                    else:
                        condition = strip_condition_prefix(chunk)
            if ':' not in line:
                return None
            role, actions_text = line.split(':', 1)
            actions = parse_actions_text(actions_text)
            return AxisStep(role.strip(), actions, condition, fallback_actions, fallback_role)
        if isinstance(raw, dict):
            role = raw.get('role') or raw.get('char') or raw.get('character') or ''
            actions = [AxisAction.from_raw(action) for action in raw.get('actions', [])]
            fallback_actions = [AxisAction.from_raw(action) for action in raw.get('fallback_actions', [])]
            fallback_role = raw.get('fallback_role') or raw.get('fallback_char') or raw.get('fallback_character') or ''
            return AxisStep(
                str(role).strip(),
                actions,
                str(raw.get('condition') or '').strip(),
                fallback_actions,
                str(fallback_role).strip(),
            )
        return None


class AxisFlowPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps: TypingList[AxisStep] = []
        self.team_keys: TypingList[str] = []
        self.profile_name = ""
        self.setMinimumHeight(240)

    def set_steps(self, steps: TypingList[AxisStep], team_keys: TypingList[str] | None = None, profile_name: str = ""):
        self.steps = steps
        self.team_keys = team_keys or []
        self.profile_name = profile_name
        self.setMinimumWidth(max(720, 260 * max(1, len(self.steps)) + 80))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            self._paint(painter, self.width(), self.height())
        except Exception as exc:
            painter.fillRect(0, 0, self.width(), self.height(), QColor("#f6f8fc"))
            painter.setPen(QColor("#e25454"))
            painter.drawText(24, 40, f"流程图预览暂时无法绘制：{exc}")

    def save_image(self, file_path: str):
        width = max(1200, 260 * max(1, len(self.steps)) + 80)
        height = 390
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#f6f8fc"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint(painter, width, height)
        painter.end()
        pixmap.save(file_path)

    def _paint(self, painter: QPainter, width: int, height: int):
        painter.fillRect(0, 0, width, height, QColor("#f6f8fc"))
        painter.setPen(QPen(QColor("#20283a")))
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(24, 34, f"自定义打轴流程图：{self.profile_name or '未命名轴'}")

        small_font = QFont()
        small_font.setPointSize(8)
        painter.setFont(small_font)
        painter.setPen(QColor("#707a8e"))
        if self.team_keys:
            painter.drawText(24, 58, "队伍：" + " → ".join(role_display(key) for key in self.team_keys))

        if not self.steps:
            painter.drawText(24, 105, "还没有步骤。先选择/新建一套队伍轴，再添加动作。")
            return

        card_w = 230
        card_h = 170
        gap = 34
        top = 86
        left = 24
        palette = ["#8c5cf6", "#4369ff", "#1fac6d", "#f59940", "#e25454", "#465064"]
        role_colors = {role_key: QColor(palette[index % len(palette)]) for index, role_key in enumerate(self.team_keys)}

        for index, step in enumerate(self.steps):
            x = left + index * (card_w + gap)
            color = role_colors.get(step.role, QColor("#465064"))
            light = QColor(color)
            light.setAlpha(38)

            painter.setPen(QPen(color, 2))
            painter.setBrush(light)
            painter.drawRoundedRect(x, top, card_w, card_h, 14, 14)

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x + 12, top + 12, 92, 34, 15, 15)
            painter.setPen(QColor("white"))
            role_font = QFont()
            role_font.setPointSize(10)
            role_font.setBold(True)
            painter.setFont(role_font)
            painter.drawText(x + 22, top + 35, role_display(step.role)[:5])

            painter.setPen(QColor("#707a8e"))
            painter.setFont(small_font)
            condition = step.condition.strip() or "无条件"
            painter.drawText(x + 12, top + 65, condition[:26])

            painter.setPen(QColor("#20283a"))
            action_font = QFont()
            action_font.setPointSize(9)
            painter.setFont(action_font)
            y = top + 94
            for action in step.actions[:4]:
                painter.drawText(x + 18, y, f"• {action.to_script()}")
                y += 22
            if len(step.actions) > 4:
                painter.drawText(x + 18, y, f"… 还有 {len(step.actions) - 4} 个动作")
                y += 22
            if step.fallback_actions:
                fallback_role = role_display(step.fallback_role or step.role)
                fallback_text = ", ".join(action.to_script() for action in step.fallback_actions[:2])
                painter.setPen(QColor("#e25454"))
                painter.drawText(x + 18, min(y, top + card_h - 14), f"未满足→{fallback_role}: {fallback_text[:18]}")

            if index < len(self.steps) - 1:
                ax1 = x + card_w + 6
                ay = top + card_h // 2
                ax2 = x + card_w + gap - 8
                painter.setPen(QPen(QColor("#bec6d6"), 3))
                painter.drawLine(ax1, ay, ax2, ay)
                painter.setBrush(QColor("#bec6d6"))
                painter.drawPolygon(QPolygon([
                    QPoint(ax2, ay),
                    QPoint(ax2 - 10, ay - 6),
                    QPoint(ax2 - 10, ay + 6),
                ]))

        if len(self.steps) > 1:
            first_x = left + card_w // 2
            last_x = left + (len(self.steps) - 1) * (card_w + gap) + card_w // 2
            loop_y = top + card_h + 48
            painter.setPen(QPen(QColor("#f59940"), 3))
            painter.drawLine(last_x, top + card_h + 10, last_x, loop_y)
            painter.drawLine(last_x, loop_y, first_x, loop_y)
            painter.drawLine(first_x, loop_y, first_x, top + card_h + 10)
            painter.setBrush(QColor("#f59940"))
            painter.drawPolygon(QPolygon([
                QPoint(first_x, top + card_h + 10),
                QPoint(first_x - 7, top + card_h + 22),
                QPoint(first_x + 7, top + card_h + 22),
            ]))
            painter.drawText((first_x + last_x) // 2 - 45, loop_y + 24, "循环下一轮")


class CustomAxisEditorWidget(QWidget):
    def __init__(
            self,
            script_file: str,
            image_file: str,
            profiles_file: str = 'configs/custom_axis_profiles.json',
            parent=None,
            close_on_save: bool = False,
    ):
        super().__init__(parent)
        self.script_file = Path(script_file)
        self.image_file = Path(image_file)
        self.profiles_file = Path(profiles_file)
        self.close_on_save = close_on_save
        self.profiles: TypingList[dict] = []
        self.current_profile_index = 0
        self.current_axis_phase = "startup"
        self.startup_steps: TypingList[AxisStep] = []
        self.loop_steps: TypingList[AxisStep] = []
        self.current_actions: TypingList[AxisAction] = []
        self.current_fallback_actions: TypingList[AxisAction] = []
        self.current_fallback_role = ""
        self.editing_step_index: int | None = None
        self.team_keys: TypingList[str] = list(DEFAULT_TEAM_KEYS)
        self.saved_script_path = ""
        self.saved_image_path = ""
        self.saved_profiles_path = ""
        self._refreshing_profiles = False

        self._load_profiles()
        self._build_ui()
        self._apply_program_style()
        self._load_profile_to_editor(0)
        self._refresh_ui()

    def _new_default_profile(self, name: str = "默认队伍轴"):
        return {
            'name': name,
            'team': list(DEFAULT_TEAM_KEYS),
            'startup_steps': [],
            'loop_steps': [
                {'role': 'Chisa', 'actions': [{'name': 'q'}, {'name': 'r'}, {'name': 'e'}], 'condition': '千咲.buff<=2'},
                {'role': 'Denia', 'actions': [{'name': 'e'}, {'name': 'r'}, {'name': 'q'}], 'condition': '达尼亚.buff<=2'},
                {'role': 'Aemeath', 'actions': [{'name': 'e'}, {'name': 'r'}, {'name': 'q'}, {'name': 'attack', 'value': 0.8}], 'condition': ''},
            ],
        }

    def _load_profiles(self):
        if self.profiles_file.exists():
            try:
                data = json.loads(self.profiles_file.read_text(encoding='utf-8'))
                if isinstance(data, dict) and isinstance(data.get('profiles'), list):
                    self.profiles = data['profiles']
                elif isinstance(data, list):
                    self.profiles = data
                elif isinstance(data, dict) and data.get('team') and data.get('steps'):
                    self.profiles = [data]
            except Exception:
                self.profiles = []
        if not self.profiles and self.script_file.exists():
            text = self.script_file.read_text(encoding='utf-8')
            sections = self._parse_script_sections(text)
            steps = sections['startup'] + sections['loop']
            team = []
            for step in steps:
                if step.role not in team:
                    team.append(step.role)
            self.profiles = [{
                'name': default_profile_name(team[:3] or DEFAULT_TEAM_KEYS),
                'team': team[:3] or list(DEFAULT_TEAM_KEYS),
                'startup_steps': [self._step_to_dict(step) for step in sections['startup']],
                'loop_steps': [self._step_to_dict(step) for step in sections['loop']],
            }]
        if not self.profiles:
            self.profiles = [self._new_default_profile()]

    def _build_ui(self):
        root = QHBoxLayout(self)

        left = QVBoxLayout()
        root.addLayout(left, 1)

        profile_box = QGroupBox("-1. 轴配置列表")
        profile_layout = QVBoxLayout(profile_box)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        profile_layout.addWidget(self.profile_combo)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名称"))
        self.profile_name_edit = QLineEdit()
        self.profile_name_edit.editingFinished.connect(self._save_editor_to_current_profile)
        name_row.addWidget(self.profile_name_edit, 1)
        profile_layout.addLayout(name_row)
        profile_btn_row = QHBoxLayout()
        new_profile_btn = QPushButton("新建")
        new_profile_btn.clicked.connect(self._new_profile)
        profile_btn_row.addWidget(new_profile_btn)
        save_profile_btn = QPushButton("保存")
        save_profile_btn.clicked.connect(self._save_profiles)
        profile_btn_row.addWidget(save_profile_btn)
        copy_profile_btn = QPushButton("复制")
        copy_profile_btn.clicked.connect(self._copy_profile)
        profile_btn_row.addWidget(copy_profile_btn)
        delete_profile_btn = QPushButton("删除")
        delete_profile_btn.clicked.connect(self._delete_profile)
        profile_btn_row.addWidget(delete_profile_btn)
        profile_layout.addLayout(profile_btn_row)
        left.addWidget(profile_box)

        team_box = QGroupBox("0. 自定义队伍，必须 3 人")
        team_layout = QVBoxLayout(team_box)
        choose_row = QHBoxLayout()
        self.character_combo = QComboBox()
        for display, key in CHARACTER_OPTIONS:
            self.character_combo.addItem(display, key)
        choose_row.addWidget(self.character_combo, 1)
        add_team_btn = QPushButton("添加到队伍")
        add_team_btn.clicked.connect(self._add_team_member)
        choose_row.addWidget(add_team_btn)
        team_layout.addLayout(choose_row)
        self.team_list = QListWidget()
        self.team_list.setMaximumHeight(90)
        team_layout.addWidget(self.team_list)
        team_btn_row = QHBoxLayout()
        remove_team_btn = QPushButton("移除")
        remove_team_btn.clicked.connect(self._remove_team_member)
        team_btn_row.addWidget(remove_team_btn)
        up_team_btn = QPushButton("上移")
        up_team_btn.clicked.connect(lambda: self._move_team_member(-1))
        team_btn_row.addWidget(up_team_btn)
        down_team_btn = QPushButton("下移")
        down_team_btn.clicked.connect(lambda: self._move_team_member(1))
        team_btn_row.addWidget(down_team_btn)
        team_layout.addLayout(team_btn_row)
        left.addWidget(team_box)

        phase_box = QGroupBox("1. 选择编辑段")
        phase_layout = QFormLayout(phase_box)
        self.axis_phase_combo = QComboBox()
        for key, label in AXIS_PHASES:
            self.axis_phase_combo.addItem(label, key)
        self.axis_phase_combo.currentIndexChanged.connect(self._on_axis_phase_changed)
        phase_layout.addRow("轴段", self.axis_phase_combo)
        left.addWidget(phase_box)

        role_box = QGroupBox("2. 选择当前步骤角色")
        role_layout = QFormLayout(role_box)
        self.role_combo = QComboBox()
        role_layout.addRow("角色", self.role_combo)
        left.addWidget(role_box)

        action_box = QGroupBox("3. 点击动作按钮")
        action_layout = QVBoxLayout(action_box)
        action_buttons = QGridLayout()
        action_buttons.setHorizontalSpacing(8)
        action_buttons.setVerticalSpacing(8)
        for index, (label, script_name) in enumerate(ACTION_LABELS.items()):
            btn = QPushButton(label)
            btn.setMinimumWidth(76)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _=False, name=script_name: self._add_action(name))
            action_buttons.addWidget(btn, index // 5, index % 5)
        action_layout.addLayout(action_buttons)

        amount_row = QHBoxLayout()
        count_label = QLabel("动作次数")
        count_label.setMinimumWidth(72)
        amount_row.addWidget(count_label)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 20)
        self.count_spin.setValue(1)
        self.count_spin.setMinimumWidth(96)
        amount_row.addWidget(self.count_spin)
        duration_label = QLabel("时长/秒")
        duration_label.setMinimumWidth(72)
        amount_row.addWidget(duration_label)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setDecimals(2)
        self.duration_spin.setRange(0.01, 30)
        self.duration_spin.setSingleStep(0.01)
        self.duration_spin.setValue(0.8)
        self.duration_spin.setMinimumWidth(116)
        self.duration_spin.setReadOnly(False)
        self.duration_spin.setKeyboardTracking(False)
        self.duration_spin.setToolTip("可手动输入秒数，最多两位小数。")
        self.duration_spin.valueChanged.connect(self._update_selected_action_duration)
        amount_row.addWidget(self.duration_spin)
        action_layout.addLayout(amount_row)

        self.action_list = QListWidget()
        self.action_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.action_list.setDefaultDropAction(Qt.MoveAction)
        self.action_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.action_list.currentRowChanged.connect(self._on_current_action_changed)
        self.action_list.model().rowsMoved.connect(self._sync_current_actions_from_list)
        action_layout.addWidget(self.action_list)
        action_manage_row = QHBoxLayout()
        delete_action_btn = QPushButton("删除选中动作")
        delete_action_btn.clicked.connect(self._delete_selected_action)
        action_manage_row.addWidget(delete_action_btn)
        up_action_btn = QPushButton("上移")
        up_action_btn.clicked.connect(lambda: self._move_selected_action(-1))
        action_manage_row.addWidget(up_action_btn)
        down_action_btn = QPushButton("下移")
        down_action_btn.clicked.connect(lambda: self._move_selected_action(1))
        action_manage_row.addWidget(down_action_btn)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_current_actions)
        action_manage_row.addWidget(clear_btn)
        action_layout.addLayout(action_manage_row)
        left.addWidget(action_box)

        condition_box = QGroupBox("4. 设置执行条件，可留空")
        condition_layout = QVBoxLayout(condition_box)
        condition_form = QFormLayout()
        self.condition_combo = QComboBox()
        self.condition_combo.setEditable(True)
        self.condition_combo.addItems(DEFAULT_CONDITIONS)
        condition_form.addRow("条件", self.condition_combo)
        condition_layout.addLayout(condition_form)

        condition_layout.addWidget(QLabel("条件未满足时的小循环动作"))
        fallback_role_form = QFormLayout()
        self.fallback_role_combo = QComboBox()
        fallback_role_form.addRow("小循环角色", self.fallback_role_combo)
        condition_layout.addLayout(fallback_role_form)
        fallback_amount_row = QHBoxLayout()
        fallback_duration_label = QLabel("小循环时长/秒")
        fallback_duration_label.setMinimumWidth(104)
        fallback_amount_row.addWidget(fallback_duration_label)
        self.fallback_duration_spin = QDoubleSpinBox()
        self.fallback_duration_spin.setDecimals(2)
        self.fallback_duration_spin.setRange(0.01, 30)
        self.fallback_duration_spin.setSingleStep(0.01)
        self.fallback_duration_spin.setValue(3.0)
        self.fallback_duration_spin.setMinimumWidth(116)
        self.fallback_duration_spin.setReadOnly(False)
        self.fallback_duration_spin.setKeyboardTracking(False)
        self.fallback_duration_spin.setToolTip("只影响下面小循环动作的秒数，最多两位小数。")
        self.fallback_duration_spin.valueChanged.connect(self._update_selected_fallback_action_duration)
        fallback_amount_row.addWidget(self.fallback_duration_spin)
        fallback_amount_row.addStretch(1)
        condition_layout.addLayout(fallback_amount_row)
        fallback_buttons = QGridLayout()
        fallback_buttons.setHorizontalSpacing(8)
        fallback_buttons.setVerticalSpacing(8)
        for index, (label, script_name) in enumerate(FALLBACK_ACTION_LABELS.items()):
            btn = QPushButton(label)
            btn.setMinimumWidth(92)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _=False, name=script_name: self._add_fallback_action(name))
            fallback_buttons.addWidget(btn, index // 4, index % 4)
        condition_layout.addLayout(fallback_buttons)
        self.fallback_action_list = QListWidget()
        self.fallback_action_list.setMaximumHeight(70)
        self.fallback_action_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.fallback_action_list.setDefaultDropAction(Qt.MoveAction)
        self.fallback_action_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fallback_action_list.currentRowChanged.connect(self._on_fallback_action_changed)
        self.fallback_action_list.model().rowsMoved.connect(self._sync_current_fallback_actions_from_list)
        condition_layout.addWidget(self.fallback_action_list)
        fallback_manage_row = QHBoxLayout()
        delete_fallback_btn = QPushButton("删除小循环动作")
        delete_fallback_btn.clicked.connect(self._delete_selected_fallback_action)
        fallback_manage_row.addWidget(delete_fallback_btn)
        clear_fallback_btn = QPushButton("清空小循环")
        clear_fallback_btn.clicked.connect(self._clear_fallback_actions)
        fallback_manage_row.addWidget(clear_fallback_btn)
        condition_layout.addLayout(fallback_manage_row)
        left.addWidget(condition_box)

        right = QVBoxLayout()
        root.addLayout(right, 2)

        self.preview = AxisFlowPreview()
        right.addWidget(self.preview, 2)

        self.steps_box = QGroupBox("流程步骤")
        steps_layout = QVBoxLayout(self.steps_box)
        self.step_list = QListWidget()
        self.step_list.currentRowChanged.connect(self._load_selected_step_for_edit)
        steps_layout.addWidget(self.step_list)
        row = QHBoxLayout()
        self.append_step_btn = QPushButton("添加到末尾")
        self.append_step_btn.setObjectName("primaryButton")
        self.append_step_btn.setToolTip("把左侧当前动作追加到当前轴段末尾。")
        self.append_step_btn.clicked.connect(self._append_step)
        row.addWidget(self.append_step_btn)
        self.add_step_btn = QPushButton("插入到选中步骤前")
        self.add_step_btn.setToolTip("先在右侧流程步骤里选择一个步骤，再把左侧当前动作插入到该步骤前。")
        self.add_step_btn.clicked.connect(self._add_step)
        row.addWidget(self.add_step_btn)
        update_step_btn = QPushButton("更新选中步骤")
        update_step_btn.clicked.connect(self._update_selected_step)
        row.addWidget(update_step_btn)
        delete_step_btn = QPushButton("删除选中步骤")
        delete_step_btn.setObjectName("dangerButton")
        delete_step_btn.clicked.connect(self._delete_selected_step)
        row.addWidget(delete_step_btn)
        steps_layout.addLayout(row)
        right.addWidget(self.steps_box, 1)

        script_box = QGroupBox("当前轴自动生成脚本")
        script_layout = QVBoxLayout(script_box)
        self.script_text = QTextEdit()
        self.script_text.setMinimumHeight(120)
        script_layout.addWidget(self.script_text)
        right.addWidget(script_box, 1)

        bottom = QHBoxLayout()
        save_script_btn = QPushButton("保存当前轴脚本")
        save_script_btn.clicked.connect(self._save_script)
        bottom.addWidget(save_script_btn)

        save_image_btn = QPushButton("保存当前轴图片")
        save_image_btn.clicked.connect(self._save_image)
        bottom.addWidget(save_image_btn)

        save_profiles_btn = QPushButton("保存全部队伍轴")
        save_profiles_btn.clicked.connect(self._save_profiles)
        bottom.addWidget(save_profiles_btn)

        save_all_btn = QPushButton("保存全部并关闭" if self.close_on_save else "保存全部")
        save_all_btn.clicked.connect(self._save_all_and_close)
        bottom.addWidget(save_all_btn)
        right.addLayout(bottom)

        self._refresh_profile_combo()

    def _apply_program_style(self):
        self.setObjectName("customAxisEditor")
        self.setStyleSheet("""
            QWidget#customAxisEditor {
                background: transparent;
            }
            QGroupBox {
                border: 1px solid rgba(32, 40, 58, 36);
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px 10px 10px 10px;
                background: rgba(255, 255, 255, 216);
                color: #20283a;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QPushButton {
                border: 1px solid rgba(67, 105, 255, 54);
                border-radius: 6px;
                padding: 6px 10px;
                background: #ffffff;
                color: #20283a;
            }
            QPushButton:hover {
                background: #f3f6ff;
                border-color: rgba(67, 105, 255, 120);
            }
            QPushButton#primaryButton {
                background: #4369ff;
                color: #ffffff;
                border-color: #4369ff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background: #3157ea;
            }
            QPushButton#dangerButton {
                border-color: rgba(226, 84, 84, 90);
                color: #b62d2d;
            }
            QLabel {
                color: #20283a;
                font-weight: 500;
            }
            QLabel#hintLabel {
                color: #707a8e;
                font-weight: 400;
            }
            QListWidget, QTextEdit, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
                border: 1px solid rgba(32, 40, 58, 36);
                border-radius: 6px;
                background: #ffffff;
                selection-background-color: #dfe6ff;
                selection-color: #20283a;
            }
        """)

    def _profile_name(self, profile):
        return profile.get('name') or default_profile_name(profile.get('team') or [])

    def _refresh_profile_combo(self):
        self._refreshing_profiles = True
        self.profile_combo.clear()
        for index, profile in enumerate(self.profiles):
            team_text = " → ".join(role_display(key) for key in profile.get('team', []))
            self.profile_combo.addItem(f"{index + 1}. {self._profile_name(profile)} [{team_text}]", index)
        if self.profiles:
            self.current_profile_index = max(0, min(self.current_profile_index, len(self.profiles) - 1))
            self.profile_combo.setCurrentIndex(self.current_profile_index)
        self._refreshing_profiles = False

    def _on_profile_changed(self, index):
        if self._refreshing_profiles or index < 0:
            return
        self._save_editor_to_current_profile()
        self._load_profile_to_editor(index)
        self._refresh_ui()

    def _on_axis_phase_changed(self, index):
        if index < 0:
            return
        self.current_axis_phase = self.axis_phase_combo.currentData(Qt.UserRole) or "startup"
        self.editing_step_index = None
        self.current_actions.clear()
        self.current_fallback_actions.clear()
        self.current_fallback_role = ""
        self._refresh_ui()

    def _new_profile(self):
        self._save_editor_to_current_profile()
        profile = self._new_default_profile(f"新队伍轴 {len(self.profiles) + 1}")
        self.profiles.append(profile)
        self.current_profile_index = len(self.profiles) - 1
        self._refresh_profile_combo()
        self._load_profile_to_editor(self.current_profile_index)
        self._refresh_ui()

    def _copy_profile(self):
        self._save_editor_to_current_profile()
        profile = json.loads(json.dumps(self.profiles[self.current_profile_index], ensure_ascii=False))
        profile['name'] = f"{self._profile_name(profile)} 副本"
        self.profiles.append(profile)
        self.current_profile_index = len(self.profiles) - 1
        self._refresh_profile_combo()
        self._load_profile_to_editor(self.current_profile_index)
        self._refresh_ui()

    def _delete_profile(self):
        if len(self.profiles) <= 1:
            QMessageBox.information(self, "提示", "至少保留一套队伍轴。")
            return
        self.profiles.pop(self.current_profile_index)
        self.current_profile_index = max(0, min(self.current_profile_index, len(self.profiles) - 1))
        self._refresh_profile_combo()
        self._load_profile_to_editor(self.current_profile_index)
        self._refresh_ui()

    def _load_profile_to_editor(self, index: int):
        if not self.profiles:
            self.profiles = [self._new_default_profile()]
        self.current_profile_index = max(0, min(index, len(self.profiles) - 1))
        profile = self.profiles[self.current_profile_index]
        self.profile_name_edit.setText(self._profile_name(profile))
        self.team_keys = list(profile.get('team') or DEFAULT_TEAM_KEYS)[:3]
        self.startup_steps = self._steps_from_raw_list(profile.get('startup_steps') or profile.get('start_steps') or [])
        loop_raw_steps = profile.get('loop_steps')
        if loop_raw_steps is None:
            loop_raw_steps = profile.get('steps') or []
        self.loop_steps = self._steps_from_raw_list(loop_raw_steps)
        self.current_actions.clear()
        self.current_fallback_actions.clear()
        self.current_fallback_role = ""
        self.editing_step_index = None

    def _steps_from_raw_list(self, raw_steps) -> TypingList[AxisStep]:
        steps = []
        for raw_step in raw_steps or []:
            step = AxisStep.from_raw(raw_step)
            if step and step.actions:
                steps.append(step)
        return steps

    def _save_editor_to_current_profile(self):
        if not self.profiles:
            return
        index = max(0, min(self.current_profile_index, len(self.profiles) - 1))
        startup_steps = [self._step_to_dict(step) for step in self.startup_steps]
        loop_steps = [self._step_to_dict(step) for step in self.loop_steps]
        self.profiles[index] = {
            'name': self.profile_name_edit.text().strip() or default_profile_name(self.team_keys),
            'team': list(self.team_keys),
            'startup_steps': startup_steps,
            'loop_steps': loop_steps,
            'steps': loop_steps,
        }

    def _step_to_dict(self, step: AxisStep):
        return {
            'role': step.role,
            'actions': [asdict(action) for action in step.actions],
            'condition': step.condition,
            'fallback_actions': [asdict(action) for action in (step.fallback_actions or [])],
            'fallback_role': step.fallback_role,
        }

    def _parse_script(self, text: str) -> TypingList[AxisStep]:
        sections = self._parse_script_sections(text, default_section='loop')
        return sections['startup'] + sections['loop']

    def _parse_script_sections(self, text: str, default_section: str = 'loop') -> dict[str, TypingList[AxisStep]]:
        sections = {'startup': [], 'loop': []}
        current_section = default_section if default_section in sections else 'loop'
        for raw in text.splitlines():
            line = raw.strip()
            lowered = line.lower()
            if not line:
                continue
            if line.startswith('#'):
                if '启动轴' in line or 'start' in lowered or 'startup' in lowered:
                    current_section = 'startup'
                elif '循环轴' in line or 'loop' in lowered:
                    current_section = 'loop'
                continue
            step = AxisStep.from_raw(line)
            if step and step.actions:
                sections[current_section].append(step)
        return sections

    def _sync_script_text_to_steps(self):
        sections = self._parse_script_sections(self.script_text.toPlainText(), default_section=self.current_axis_phase)
        self.startup_steps = sections['startup']
        self.loop_steps = sections['loop']
        self.current_actions.clear()
        self.current_fallback_actions.clear()
        self.current_fallback_role = ""
        self.editing_step_index = None

    def _team_member_key_from_combo(self) -> str:
        return self.character_combo.currentData(Qt.UserRole)

    def _role_key_from_combo(self) -> str:
        return self.role_combo.currentData(Qt.UserRole) or self.role_combo.currentText()

    def _fallback_role_key_from_combo(self) -> str:
        if hasattr(self, 'fallback_role_combo') and self.fallback_role_combo.count():
            return self.fallback_role_combo.currentData(Qt.UserRole) or self.fallback_role_combo.currentText()
        return self._role_key_from_combo()

    def _phase_label(self, phase: str | None = None) -> str:
        phase = phase or self.current_axis_phase
        return dict(AXIS_PHASES).get(phase, "启动轴")

    def _active_steps(self) -> TypingList[AxisStep]:
        return self.startup_steps if self.current_axis_phase == "startup" else self.loop_steps

    def _add_team_member(self):
        key = self._team_member_key_from_combo()
        if key in self.team_keys:
            QMessageBox.information(self, "提示", "这个角色已经在当前队伍里。")
            return
        if len(self.team_keys) >= 3:
            QMessageBox.information(self, "提示", "每套队伍轴必须 3 名角色。请先移除一个角色。")
            return
        self.team_keys.append(key)
        self._refresh_ui()

    def _remove_team_member(self):
        row = self.team_list.currentRow()
        if 0 <= row < len(self.team_keys):
            removed = self.team_keys.pop(row)
            self.startup_steps = [step for step in self.startup_steps if step.role != removed]
            self.loop_steps = [step for step in self.loop_steps if step.role != removed]
            self._refresh_ui()

    def _move_team_member(self, direction: int):
        row = self.team_list.currentRow()
        new_row = row + direction
        if 0 <= row < len(self.team_keys) and 0 <= new_row < len(self.team_keys):
            self.team_keys[row], self.team_keys[new_row] = self.team_keys[new_row], self.team_keys[row]
            self._refresh_ui()
            self.team_list.setCurrentRow(new_row)

    def _add_action(self, name: str):
        if name == 'e_wait':
            self.current_actions.append(AxisAction('e', self.duration_spin.value()))
        elif name in TIMED_ACTION_NAMES:
            duration = DEFAULT_ACTION_DURATIONS[name] if name in DEFAULT_ACTION_DURATIONS else self.duration_spin.value()
            self.current_actions.append(AxisAction(name, duration))
        else:
            for _ in range(self.count_spin.value()):
                self.current_actions.append(AxisAction(name))
        self._refresh_current_actions()
        if self.current_actions:
            self.action_list.setCurrentRow(len(self.current_actions) - 1)

    def _clear_current_actions(self):
        self.current_actions.clear()
        self.editing_step_index = None
        self._refresh_current_actions()

    def _add_fallback_action(self, name: str):
        if name == 'e_wait':
            self.current_fallback_actions.append(AxisAction('e', self.fallback_duration_spin.value()))
        elif name in TIMED_ACTION_NAMES:
            self.current_fallback_actions.append(AxisAction(name, self.fallback_duration_spin.value()))
        else:
            for _ in range(self.count_spin.value()):
                self.current_fallback_actions.append(AxisAction(name))
        self._refresh_current_fallback_actions()
        if self.current_fallback_actions:
            self.fallback_action_list.setCurrentRow(len(self.current_fallback_actions) - 1)

    def _clear_fallback_actions(self):
        self.current_fallback_actions.clear()
        self.current_fallback_role = ""
        self._refresh_current_fallback_actions()

    def _delete_selected_fallback_action(self):
        row = self.fallback_action_list.currentRow()
        if not (0 <= row < len(self.current_fallback_actions)):
            return
        self.current_fallback_actions.pop(row)
        self._refresh_current_fallback_actions()
        if self.current_fallback_actions:
            self.fallback_action_list.setCurrentRow(min(row, len(self.current_fallback_actions) - 1))

    def _delete_selected_action(self):
        row = self.action_list.currentRow()
        if not (0 <= row < len(self.current_actions)):
            return
        self.current_actions.pop(row)
        self._refresh_current_actions()
        if self.current_actions:
            self.action_list.setCurrentRow(min(row, len(self.current_actions) - 1))

    def _move_selected_action(self, direction: int):
        row = self.action_list.currentRow()
        new_row = row + direction
        if not (0 <= row < len(self.current_actions) and 0 <= new_row < len(self.current_actions)):
            return
        self.current_actions[row], self.current_actions[new_row] = self.current_actions[new_row], self.current_actions[row]
        self._refresh_current_actions()
        self.action_list.setCurrentRow(new_row)

    def _sync_current_actions_from_list(self, *args):
        reordered = []
        for row in range(self.action_list.count()):
            action = self.action_list.item(row).data(Qt.UserRole)
            if isinstance(action, AxisAction):
                reordered.append(AxisAction(action.name, action.value))
        if len(reordered) == len(self.current_actions):
            self.current_actions = reordered

    def _sync_current_fallback_actions_from_list(self, *args):
        reordered = []
        for row in range(self.fallback_action_list.count()):
            action = self.fallback_action_list.item(row).data(Qt.UserRole)
            if isinstance(action, AxisAction):
                reordered.append(AxisAction(action.name, action.value))
        if len(reordered) == len(self.current_fallback_actions):
            self.current_fallback_actions = reordered

    def _new_step_from_editor(self):
        return AxisStep(
            role=self._role_key_from_combo(),
            actions=list(self.current_actions),
            condition=self.condition_combo.currentText().strip(),
            fallback_actions=list(self.current_fallback_actions),
            fallback_role=self._fallback_role_key_from_combo() if self.current_fallback_actions else "",
        )

    def _can_add_step(self):
        if len(self.team_keys) != 3:
            QMessageBox.information(self, "提示", "请先配置完整 3 人队伍。")
            return False
        if not self.current_actions:
            QMessageBox.information(self, "提示", "请先点击动作按钮添加至少一个动作。")
            return False
        return True

    def _append_step(self):
        if not self._can_add_step():
            return
        steps = self._active_steps()
        steps.append(self._new_step_from_editor())
        self.current_actions.clear()
        self.current_fallback_actions.clear()
        self.current_fallback_role = ""
        self.editing_step_index = len(steps) - 1
        self._refresh_ui()

    def _add_step(self):
        if not self._can_add_step():
            return
        steps = self._active_steps()
        insert_at = self.step_list.currentRow()
        if not (0 <= insert_at < len(steps)):
            insert_at = self.editing_step_index if self.editing_step_index is not None else len(steps)
        if not (0 <= insert_at < len(steps)):
            insert_at = len(steps)
        steps.insert(insert_at, self._new_step_from_editor())
        self.current_actions.clear()
        self.current_fallback_actions.clear()
        self.current_fallback_role = ""
        self.editing_step_index = insert_at
        self._refresh_ui()

    def _update_selected_step(self):
        steps = self._active_steps()
        row = self.editing_step_index
        if row is None:
            row = self.step_list.currentRow()
        if not (0 <= row < len(steps)):
            QMessageBox.information(self, "提示", "请先在右侧选择要更新的流程步骤。")
            return
        if not self.current_actions:
            QMessageBox.information(self, "提示", "当前动作为空，不能更新步骤。")
            return
        steps[row] = AxisStep(
            role=self._role_key_from_combo(),
            actions=list(self.current_actions),
            condition=self.condition_combo.currentText().strip(),
            fallback_actions=list(self.current_fallback_actions),
            fallback_role=self._fallback_role_key_from_combo() if self.current_fallback_actions else "",
        )
        self.editing_step_index = row
        self._refresh_ui()

    def _delete_selected_step(self):
        row = self.step_list.currentRow()
        steps = self._active_steps()
        if 0 <= row < len(steps):
            steps.pop(row)
            self.editing_step_index = None
            self.current_actions.clear()
            self.current_fallback_actions.clear()
            self.current_fallback_role = ""
            self._refresh_ui()

    def _load_selected_step_for_edit(self, row: int):
        steps = self._active_steps()
        if not (0 <= row < len(steps)):
            return
        step = steps[row]
        self.editing_step_index = row
        if step.role in self.team_keys:
            self.role_combo.setCurrentIndex(self.team_keys.index(step.role))
        self.current_actions = [AxisAction(action.name, action.value) for action in step.actions]
        self.current_fallback_actions = [AxisAction(action.name, action.value) for action in (step.fallback_actions or [])]
        self.current_fallback_role = step.fallback_role or step.role
        self.condition_combo.setCurrentText(step.condition)
        if self.current_fallback_role in self.team_keys:
            self.fallback_role_combo.setCurrentIndex(self.team_keys.index(self.current_fallback_role))
        self._refresh_current_actions()
        self._refresh_current_fallback_actions()
        if self.current_actions:
            self.action_list.setCurrentRow(0)

    def _on_current_action_changed(self, row: int):
        if not (0 <= row < len(self.current_actions)):
            return
        value = self.current_actions[row].value
        if value is not None:
            self.duration_spin.blockSignals(True)
            self.duration_spin.setValue(float(value))
            self.duration_spin.blockSignals(False)

    def _on_fallback_action_changed(self, row: int):
        if not (0 <= row < len(self.current_fallback_actions)):
            return
        value = self.current_fallback_actions[row].value
        if value is not None:
            self.fallback_duration_spin.blockSignals(True)
            self.fallback_duration_spin.setValue(float(value))
            self.fallback_duration_spin.blockSignals(False)

    def _update_selected_action_duration(self, value: float):
        row = self.action_list.currentRow()
        if not (0 <= row < len(self.current_actions)):
            return
        action = self.current_actions[row]
        if action.value is None and action.name not in TIMED_ACTION_NAMES | {'space'}:
            return
        action.value = value
        self._refresh_current_actions()
        self.action_list.setCurrentRow(row)

    def _update_selected_fallback_action_duration(self, value: float):
        row = self.fallback_action_list.currentRow()
        if not (0 <= row < len(self.current_fallback_actions)):
            return
        action = self.current_fallback_actions[row]
        if action.value is None and action.name not in TIMED_ACTION_NAMES | {'space'}:
            return
        action.value = value
        self._refresh_current_fallback_actions()
        self.fallback_action_list.setCurrentRow(row)

    def _refresh_team_list(self):
        self.team_list.clear()
        for index, key in enumerate(self.team_keys, start=1):
            self.team_list.addItem(QListWidgetItem(f"{index}. {CHARACTER_DISPLAY_BY_KEY.get(key, key)}"))

    def _refresh_role_combo(self):
        current = self._role_key_from_combo() if self.role_combo.count() else None
        self.role_combo.clear()
        for index, key in enumerate(self.team_keys, start=1):
            self.role_combo.addItem(f"{index}. {CHARACTER_DISPLAY_BY_KEY.get(key, key)}", key)
        if current in self.team_keys:
            self.role_combo.setCurrentIndex(self.team_keys.index(current))

    def _refresh_fallback_role_combo(self):
        current = self.current_fallback_role or self._fallback_role_key_from_combo()
        if current not in self.team_keys:
            current = self._role_key_from_combo()
        self.fallback_role_combo.blockSignals(True)
        self.fallback_role_combo.clear()
        for index, key in enumerate(self.team_keys, start=1):
            self.fallback_role_combo.addItem(f"{index}. {CHARACTER_DISPLAY_BY_KEY.get(key, key)}", key)
        if current in self.team_keys:
            self.fallback_role_combo.setCurrentIndex(self.team_keys.index(current))
        self.fallback_role_combo.blockSignals(False)

    def _condition_options(self):
        options = list(DEFAULT_CONDITIONS)
        for key in self.team_keys:
            name = role_display(key)
            options.extend([
                f"{name}.协奏满==1",
                f"{name}.大招==1",
                f"{name}.技能==1",
                f"{name}.声骸==1",
                f"{name}.buff<=2",
                f"{name}.buff>2",
                f"{name}.current==1",
            ])
            if key == "Aemeath":
                options.extend([
                    f"{name}.lib2<=1",
                    f"{name}.wait_lib2==1",
                ])
        deduped = []
        seen = set()
        for option in options:
            if option not in seen:
                deduped.append(option)
                seen.add(option)
        return deduped

    def _refresh_condition_combo(self):
        current = self.condition_combo.currentText().strip()
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        self.condition_combo.addItems(self._condition_options())
        if current:
            index = self.condition_combo.findText(current)
            if index >= 0:
                self.condition_combo.setCurrentIndex(index)
            else:
                self.condition_combo.setEditText(current)
        else:
            self.condition_combo.setCurrentIndex(0)
        self.condition_combo.blockSignals(False)

    def _refresh_current_actions(self):
        self.action_list.clear()
        for action in self.current_actions:
            item = QListWidgetItem(action_display(action))
            item.setToolTip(action.to_script())
            item.setData(Qt.UserRole, AxisAction(action.name, action.value))
            self.action_list.addItem(item)

    def _refresh_current_fallback_actions(self):
        self.fallback_action_list.clear()
        for action in self.current_fallback_actions:
            item = QListWidgetItem(action_display(action))
            item.setToolTip(action.to_script())
            item.setData(Qt.UserRole, AxisAction(action.name, action.value))
            self.fallback_action_list.addItem(item)

    def _refresh_ui(self):
        self._refresh_team_list()
        self._refresh_role_combo()
        self._refresh_fallback_role_combo()
        self._refresh_condition_combo()
        self._refresh_current_actions()
        self._refresh_current_fallback_actions()
        profile_name = self.profile_name_edit.text().strip() or default_profile_name(self.team_keys)
        steps = self._active_steps()
        self.preview.set_steps(steps, self.team_keys, f"{profile_name} · {self._phase_label()}")
        self.steps_box.setTitle(f"{self._phase_label()}步骤")
        selected_row = self.editing_step_index
        self.step_list.clear()
        for index, step in enumerate(steps, start=1):
            item = QListWidgetItem(f"{index}. {role_display(step.role)}: {step.to_script()}")
            item.setToolTip(step.to_script())
            self.step_list.addItem(item)
        if selected_row is not None and 0 <= selected_row < len(steps):
            self.step_list.setCurrentRow(selected_row)
        self.add_step_btn.setEnabled(self.step_list.currentRow() >= 0)
        self.script_text.setPlainText(self._to_script())

    def _to_script(self) -> str:
        profile_name = self.profile_name_edit.text().strip() or default_profile_name(self.team_keys)
        team_line = "# 队伍：" + ", ".join(self.team_keys) + "\n"
        header = (
            f"# 由自定义打轴编辑器生成\n"
            f"# 轴名称：{profile_name}\n"
            "# 启动轴：每次进战只执行一轮\n"
            "# 循环轴：启动轴结束后重复执行\n"
            "# 格式：角色: 动作1, 动作2 | 条件 条件表达式\n"
            + team_line
        )
        startup = "\n".join(step.to_script() for step in self.startup_steps)
        loop = "\n".join(step.to_script() for step in self.loop_steps)
        return f"{header}\n# ===== 启动轴 =====\n{startup}\n\n# ===== 循环轴 =====\n{loop}\n"

    def _save_script(self, notify: bool = True):
        self._sync_script_text_to_steps()
        self._save_editor_to_current_profile()
        self.script_file.parent.mkdir(parents=True, exist_ok=True)
        script = self._to_script().strip() + "\n"
        self.script_file.write_text(script, encoding='utf-8')
        self.saved_script_path = str(self.script_file)
        self._refresh_ui()
        if notify:
            QMessageBox.information(self, "已保存", f"当前轴脚本已同步到步骤并保存到：\n{self.script_file}")

    def _save_profiles(self, notify: bool = True):
        self._sync_script_text_to_steps()
        self._save_editor_to_current_profile()
        self._refresh_profile_combo()
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': 1,
            'match': 'composition',
            'profiles': self.profiles,
        }
        self.profiles_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        self.saved_profiles_path = str(self.profiles_file)
        self._refresh_ui()
        if notify:
            QMessageBox.information(self, "已保存", f"全部队伍轴已保存到：\n{self.profiles_file}")

    def _save_image(self, notify: bool = True):
        self._sync_script_text_to_steps()
        self._save_editor_to_current_profile()
        self.image_file.parent.mkdir(parents=True, exist_ok=True)
        stem = self.image_file.stem
        suffix = self.image_file.suffix or '.png'
        profile_name = self.profile_name_edit.text().strip() or default_profile_name(self.team_keys)
        safe_name = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in f"{profile_name}_{self._phase_label()}")
        image_path = self.image_file.with_name(f"{stem}_{safe_name}{suffix}")
        self._refresh_ui()
        self.preview.save_image(str(image_path))
        self.saved_image_path = str(image_path)
        if notify:
            QMessageBox.information(self, "已保存", f"当前轴图片已保存到：\n{image_path}")

    def _save_all_and_close(self):
        self._save_script(notify=False)
        self._save_profiles(notify=False)
        self._save_image(notify=False)
        QMessageBox.information(self, "已保存", "全部队伍轴、当前轴脚本和当前轴图片已保存。")
        if self.close_on_save:
            parent_window = self.window()
            if isinstance(parent_window, QDialog):
                parent_window.accept()

    def update_value(self):
        self._refresh_ui()


class CustomAxisEditorConfigItem(QWidget):
    def __init__(self, config_desc, key: str, script_file: str, image_file: str, profiles_file: str):
        super().__init__()
        self.key = key
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel(key)
        title.setObjectName('titleLabel')
        root.addWidget(title)

        if config_desc and config_desc.get(key):
            desc = QLabel(config_desc.get(key))
            desc.setObjectName('contentLabel')
            desc.setWordWrap(True)
            root.addWidget(desc)

        self.editor = CustomAxisEditorWidget(
            script_file=script_file,
            image_file=image_file,
            profiles_file=profiles_file,
            parent=self,
            close_on_save=False,
        )
        root.addWidget(self.editor)

    def update_value(self):
        self.editor.update_value()


class CustomAxisEditorDialog(QDialog):
    def __init__(self, script_file: str, image_file: str, profiles_file: str = 'configs/custom_axis_profiles.json', parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义打轴编辑器 · 多队伍小白模式")
        self.resize(1320, 860)
        layout = QVBoxLayout(self)
        self.editor = CustomAxisEditorWidget(script_file, image_file, profiles_file, self, close_on_save=True)
        layout.addWidget(self.editor)

    @property
    def saved_script_path(self):
        return self.editor.saved_script_path

    @property
    def saved_profiles_path(self):
        return self.editor.saved_profiles_path

    @property
    def saved_image_path(self):
        return self.editor.saved_image_path


def open_custom_axis_editor(script_file: str = 'configs/custom_axis_script.txt',
                            image_file: str = 'configs/custom_axis_flow.png',
                            profiles_file: str = 'configs/custom_axis_profiles.json'):
    app = QApplication.instance()
    created_app = False
    if app is None:
        app = QApplication([])
        created_app = True
    dialog = CustomAxisEditorDialog(script_file, image_file, profiles_file)
    dialog.exec()
    if created_app:
        app.quit()
    return dialog.saved_script_path or dialog.saved_profiles_path, dialog.saved_image_path
