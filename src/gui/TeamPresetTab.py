import json

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QListWidgetItem,
    QSplitter, QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    BodyLabel, CheckBox, ComboBox, FluentIcon, LineEdit, ListWidget, MessageBox,
    PlainTextEdit, PrimaryPushButton, PushButton, SimpleCardWidget,
    SingleDirectionScrollArea, ToolTipFilter,
)

from ok.gui.tasks.EditTaskTab import CodeEditor
from ok.gui.tasks.PythonHighlighter import PythonHighlighter
from ok.gui.util.app import show_info_bar
from ok.gui.widget.CustomTab import CustomTab
from src.char.CharFactory import char_dict
from src.char.CustomCharLoader import (
    load_custom_char_class_with_preset,
    read_builtin_char_code,
)
from src.gui.CharacterCodeTab import CHARACTER_DISPLAY_NAMES
from src.team_preset.TeamPresetStore import (
    TeamPreset, TeamPresetSlot, TeamPresetStore,
)

MAX_SLOTS = 3
AUTO_SAVE_DELAY_MS = 800


def global_char_setting_keys():
    """全局 Character Config 里所有可用参数键(如 'Iuno C6')。"""
    try:
        from ok.util.config import Config
        return list((Config('Character Config', {}) or {}).keys())
    except Exception as e:
        from ok import Logger
        Logger.get_logger(__name__).error(f'read Character Config keys failed: {e}')
        return []


def _slugify_role(char_name):
    return (char_name or '').strip().lower()


class _SlotEditor(QWidget):
    """一个角色位卡片:选角色 → 勾选项 → (可选)高级参数/自定义代码。"""

    def __init__(self, tab, slot_index):
        super().__init__()
        self.tab = tab
        self.slot_index = slot_index
        self.clean_code = ""
        self.code_has_unsaved_changes = False
        self.advanced_visible = False

        self.card = SimpleCardWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.slot_badge = QFrame(self.card)
        self.slot_badge.setFixedSize(26, 26)
        self.slot_badge.setStyleSheet(
            "QFrame{background:#2f6fed;border-radius:13px;color:white;}")
        badge_layout = QVBoxLayout(self.slot_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignCenter)
        self.slot_badge_label = BodyLabel(str(slot_index + 1), self.slot_badge)
        self.slot_badge_label.setStyleSheet("color:white;font-weight:600;")
        badge_layout.addWidget(self.slot_badge_label)
        header.addWidget(self.slot_badge)
        header.addSpacing(6)
        self.slot_label = BodyLabel(self.tab.tr("Slot {index}").format(index=slot_index + 1), self.card)
        header.addWidget(self.slot_label)
        header.addSpacing(12)
        self.char_combo = ComboBox(self.card)
        self.char_combo.setMinimumWidth(190)
        self.char_combo.setPlaceholderText(self.tab.tr("Pick a character…"))
        header.addWidget(self.char_combo)
        header.addStretch(1)
        self.enabled_check = CheckBox(self.tab.tr("Use this slot"), self.card)
        self.enabled_check.setChecked(True)
        header.addWidget(self.enabled_check)
        layout.addLayout(header)

        self.setting_title = BodyLabel(self.tab.tr("Character Settings"), self.card)
        layout.addWidget(self.setting_title)
        self.setting_box = QVBoxLayout()
        self.setting_box.setSpacing(4)
        layout.addLayout(self.setting_box)
        self.setting_empty_hint = BodyLabel(self.tab.tr("No extra settings for this character."), self.card)
        self.setting_empty_hint.setStyleSheet("color:rgba(128,128,128,0.8);")
        self.setting_empty_hint.setVisible(False)
        layout.addWidget(self.setting_empty_hint)

        advanced_row = QHBoxLayout()
        self.advanced_button = PushButton(self.tab.tr("Advanced Parameters (JSON)"), self.card)
        self.advanced_button.setFixedHeight(30)
        self.advanced_button.clicked.connect(self._toggle_advanced)
        advanced_row.addWidget(self.advanced_button)
        advanced_row.addStretch(1)
        layout.addLayout(advanced_row)

        self.params_edit = LineEdit(self.card)
        self.params_edit.setPlaceholderText(
            self.tab.tr('Optional JSON, e.g. {"Iuno C6": false}'))
        self.params_edit.setVisible(False)
        layout.addWidget(self.params_edit)

        self.note_edit = LineEdit(self.card)
        self.note_edit.setPlaceholderText(self.tab.tr("Note (optional)"))
        layout.addWidget(self.note_edit)

        self.code_toggle = PushButton(FluentIcon.CODE, self.tab.tr("Custom Code"), self.card)
        self.code_toggle.setFixedHeight(32)
        self.code_toggle.setToolTip(self.tab.tr("Open a full editor window for this character's code."))
        self.code_toggle.clicked.connect(self._open_code_dialog)
        layout.addWidget(self.code_toggle)

        self.char_combo.currentIndexChanged.connect(self._slot_char_changed)
        self.enabled_check.toggled.connect(self._apply_enabled_state)
        self.enabled_check.toggled.connect(self.tab._schedule_auto_save)
        self.params_edit.textChanged.connect(self.tab._schedule_auto_save)
        self.note_edit.textChanged.connect(self.tab._schedule_auto_save)

        self.code_widgets = [self.code_toggle]
        self.param_checks = []
        self._apply_enabled_state(self.enabled_check.isChecked())

    # ---------- state helpers ----------

    @staticmethod
    def _combo_data(combo, index):
        items = getattr(combo, "items", None)
        if items and 0 <= index < len(items):
            return items[index].userData or ""
        return ""

    def char_class_name(self):
        return self._combo_data(self.char_combo, self.char_combo.currentIndex())

    def is_checked_char_used_by_other(self):
        name = self.char_class_name()
        if not name:
            return None
        for other in self.tab.slot_editors:
            if other is self:
                continue
            if other.char_class_name() == name and other.enabled_check.isChecked():
                return other.slot_index
        return None

    # ---------- slot content ----------

    def _global_keys_for_char(self, char_name):
        prefix = _slugify_role(char_name)
        if not prefix:
            return []
        return [key for key in self.tab.global_setting_keys
                if _slugify_role(key.split()[0]) == prefix]

    def _rebuild_setting_checks(self):
        for widget in self.param_checks:
            widget.setParent(None)
            widget.deleteLater()
        self.param_checks = []
        char_name = self.char_class_name()
        keys = self._global_keys_for_char(char_name)
        checked_so_far = {k: True for k in self._checked_param_keys()}
        for key in keys:
            row = QWidget(self.card)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            check = CheckBox(self.tab.tr(key), row)
            check.setChecked(key in checked_so_far)
            check.toggled.connect(self.tab._schedule_auto_save)
            row_layout.addWidget(check)
            row_layout.addStretch(1)
            self.setting_box.addWidget(row)
            self.param_checks.append(row)
            row._key = key
        self.setting_empty_hint.setVisible(not keys and bool(char_name))
        self.setting_title.setVisible(bool(char_name))

    def _checked_param_keys(self):
        keys = []
        for row in self.param_checks:
            check = row.findChild(CheckBox)
            if check is not None and check.isChecked():
                keys.append(row._key)
        return keys

    def _toggle_advanced(self):
        self.advanced_visible = not self.advanced_visible
        self.params_edit.setVisible(self.advanced_visible)
        self.advanced_button.setText(
            self.tab.tr("Hide Advanced Parameters") if self.advanced_visible
            else self.tab.tr("Advanced Parameters (JSON)"))
        self.tab._schedule_auto_save()

    def _open_code_dialog(self):
        char_name = self.char_class_name()
        if not char_name:
            show_info_bar(self.window(), self.tab.tr("Pick a character first"),
                          title=self.tab.tr("Error"), error=True)
            return
        _CodeEditorDialog(self.tab, char_name, self.window()).exec()

    def _apply_enabled_state(self, checked):
        self.char_combo.setEnabled(checked)
        self.setting_title.setEnabled(checked)
        self.setting_empty_hint.setEnabled(checked)
        for row in self.param_checks:
            row.setEnabled(checked)
        self.params_edit.setEnabled(checked)
        self.note_edit.setEnabled(checked)
        self.advanced_button.setEnabled(checked)
        for widget in self.code_widgets:
            widget.setEnabled(checked)

    # ---------- code ----------

    def _slot_char_changed(self):
        duplicate = self.is_checked_char_used_by_other()
        if duplicate is not None:
            previous = self.tab._previous_slot_char.get(self.slot_index, "")
            self.char_combo.blockSignals(True)
            self._set_combo_to(previous)
            self.char_combo.blockSignals(False)
            show_info_bar(
                self.window(),
                self.tab.tr("Character already used in slot {index}").format(index=duplicate + 1),
                title=self.tab.tr("Notice"), error=True)
            return
        self._rebuild_setting_checks()
        self.tab._previous_slot_char[self.slot_index] = self.char_class_name()
        self.tab._schedule_auto_save()

    def _set_combo_to(self, char_name):
        target_index = 0
        items = getattr(self.char_combo, "items", None) or []
        for i, item in enumerate(items):
            if (item.userData or "") == char_name:
                target_index = i
                break
        self.char_combo.setCurrentIndex(target_index)

    # ---------- load / dump ----------

    def load_slot(self, slot):
        char_name = slot.char if slot else ""
        self.char_combo.blockSignals(True)
        self._set_combo_to(char_name)
        self.char_combo.blockSignals(False)
        self.enabled_check.setChecked(not slot or slot.enabled)
        self.note_edit.setText(slot.note if slot else "")
        params = dict(slot.params) if slot and slot.params else {}
        checked_keys = [k for k, v in params.items() if v]
        self._rebuild_setting_checks()
        for row in self.param_checks:
            check = row.findChild(CheckBox)
            if check is not None:
                check.setChecked(row._key in checked_keys)
        json_keys = {k: v for k, v in params.items() if k not in self._global_keys_for_char(char_name)}
        self.params_edit.setText(json.dumps(json_keys, ensure_ascii=False) if json_keys else "")
        self.advanced_visible = False
        self.params_edit.setVisible(False)
        self.advanced_button.setText(self.tab.tr("Advanced Parameters (JSON)"))
        self.code_toggle.setToolTip(self.tab.tr("Open a full editor window for this character's code."))
        self.tab._previous_slot_char[self.slot_index] = char_name
        self._apply_enabled_state(self.enabled_check.isChecked())

    def to_slot(self):
        char_name = self.char_class_name()
        params = {}
        advanced_text = self.params_edit.text().strip()
        if advanced_text:
            try:
                parsed = json.loads(advanced_text)
                if not isinstance(parsed, dict):
                    raise ValueError("params must be a JSON object")
                params.update(parsed)
            except Exception as e:
                raise ValueError(self.tab.tr("Invalid params JSON in slot {index}: {error}").format(
                    index=self.slot_index + 1, error=e))
        for key in self._checked_param_keys():
            params[key] = True
        custom_code = ""
        if self.tab.current_preset is not None and char_name:
            if TeamPresetStore.has_custom_code(self.tab.current_preset.id, char_name):
                custom_code = f"{char_name}.py"
        return TeamPresetSlot(
            char=char_name,
            enabled=self.enabled_check.isChecked(),
            note=self.note_edit.text(),
            params=params,
            custom_code=custom_code,
        )

    def reset_widgets(self):
        self.char_combo.blockSignals(True)
        self._set_combo_to("")
        self.char_combo.blockSignals(False)
        self.enabled_check.setChecked(True)
        self.note_edit.setText("")
        self.params_edit.setText("")
        self.advanced_visible = False
        self.params_edit.setVisible(False)
        self.advanced_button.setText(self.tab.tr("Advanced Parameters (JSON)"))
        for widget in self.code_widgets:
            widget.setVisible(True)
        self.code_toggle.setText(self.tab.tr("Custom Code"))
        self._rebuild_setting_checks()
        self._apply_enabled_state(True)


class _CodeEditorDialog(QDialog):
    """Full-window editor for a preset character's custom code."""

    def __init__(self, tab, char_name, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.preset = tab.current_preset
        self.char_name = char_name
        self.clean_code = ""
        self.code_has_unsaved_changes = False
        self.setModal(True)
        self.setMinimumSize(720, 520)
        self.resize(900, 680)

        self.code_editor = CodeEditor(self)
        self.code_editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = self.code_editor.font()
        font.setFamily("Consolas")
        font.setPointSize(11)
        self.code_editor.setFont(font)
        PythonHighlighter(self.code_editor.document())
        self.code_editor.textChanged.connect(self._on_text_changed)

        self.source_label = BodyLabel("", self)
        self.source_label.setStyleSheet("color:rgba(140,140,140,0.9);")

        self.status_label = BodyLabel("", self)

        reset_button = PushButton(self.tr("Reset Code"), self)
        reset_button.clicked.connect(self._reset_code)
        save_button = PrimaryPushButton(self.tr("Save Code"), self)
        save_button.clicked.connect(self._save_code)
        close_button = PushButton(self.tr("Close"), self)
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.source_label)
        layout.addWidget(self.code_editor, 1)
        footer = QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        footer.addWidget(reset_button)
        footer.addSpacing(6)
        footer.addWidget(save_button)
        footer.addWidget(close_button)
        layout.addLayout(footer)

        self._load_code()

    def _load_code(self):
        code = TeamPresetStore.read_custom_code(self.preset.id, self.char_name)
        if code is None:
            cls = self.tab.char_class_by_name.get(self.char_name)
            if cls is not None:
                code = read_builtin_char_code(cls)
            self.source_label.setText(self.tr(
                "No custom code yet - editing a copy of the builtin code. "
                "Save to create one for this team."))
        else:
            self.source_label.setText(self.tr(
                "Editing this team's custom code for this character."))
        self.code_editor.setPlainText(code or "")
        self.clean_code = self.code_editor.toPlainText()
        self.code_has_unsaved_changes = False
        display = self.tab._display_char_name(self.char_name)
        preset_name = self.preset.name if self.preset and self.preset.name else ""
        self.base_title = self.tr("Custom Code") + f" - {display}"
        if preset_name:
            self.base_title += f" ({preset_name})"
        self._refresh_title()

    def _refresh_title(self):
        title = self.base_title
        if self.code_has_unsaved_changes:
            title = "* " + title
        self.setWindowTitle(title)

    def _on_text_changed(self):
        self.code_has_unsaved_changes = self.code_editor.toPlainText() != self.clean_code
        self._refresh_title()

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color:#cf4d4d;" if error else "color:#2fa86f;")

    def _save_code(self):
        code = self.code_editor.toPlainText()
        try:
            TeamPresetStore.save_custom_code(self.preset.id, self.char_name, code)
        except Exception as e:
            self.tab.logger.error(f"save preset custom code failed: {e}")
            self._set_status(str(e), error=True)
            return
        self.clean_code = code
        self.code_has_unsaved_changes = False
        self._refresh_title()
        self._set_status(self.tr("Code saved"))
        self.tab._reload_live_char_code(self.preset.id, self.char_name)

    def _reset_code(self):
        if self.code_has_unsaved_changes:
            box = MessageBox(self.tr("Unsaved Changes"),
                             self.tr("Discard unsaved preset character code changes?"),
                             self)
            if not box.exec():
                return
        TeamPresetStore.remove_custom_code(self.preset.id, self.char_name)
        cls = self.tab.char_class_by_name.get(self.char_name)
        code = read_builtin_char_code(cls) if cls is not None else ""
        self.code_editor.setPlainText(code)
        self.clean_code = code
        self.code_has_unsaved_changes = False
        self._refresh_title()
        self._set_status(self.tr("Reset to builtin"))
        self.tab._reload_live_char_code(self.preset.id, self.char_name)

    def closeEvent(self, event):
        if self.code_has_unsaved_changes:
            box = MessageBox(self.tr("Unsaved Changes"),
                             self.tr("Discard unsaved preset character code changes?"),
                             self)
            if not box.exec():
                event.ignore()
                return
        event.accept()
        super().closeEvent(event)


class TeamPresetTab(CustomTab):

    def __init__(self):
        super().__init__()
        self.current_preset = None
        self.current_row = -1
        self.suppress_selection_guard = False
        self.slot_editors = []
        self.char_class_by_name = self._build_char_classes()
        self.char_options = self._build_char_options()
        self.global_setting_keys = global_char_setting_keys()
        self._previous_slot_char = {}
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(AUTO_SAVE_DELAY_MS)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._banner_timer = QTimer(self)
        self._banner_timer.setInterval(2000)
        self._banner_timer.timeout.connect(self._refresh_runtime_state)

        container = QWidget(self.view)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        banner = QHBoxLayout()
        self.active_badge = QFrame(container)
        self.active_badge.setFixedHeight(30)
        self.active_badge_layout = QHBoxLayout(self.active_badge)
        self.active_badge_layout.setContentsMargins(14, 0, 14, 0)
        self.active_badge_text = BodyLabel("", self.active_badge)
        self.active_badge_layout.addWidget(self.active_badge_text)
        self.active_badge_layout.addStretch(1)
        banner.addWidget(self.active_badge, 0)
        banner.addSpacing(10)
        self.banner_hint = BodyLabel(self.tr("Pick characters - the team matching your in-game lineup is used automatically."), container)
        self.banner_hint.setStyleSheet("color:rgba(140,140,140,0.9);")
        banner.addWidget(self.banner_hint)
        banner.addStretch(1)
        outer.addLayout(banner)

        splitter = QSplitter(Qt.Horizontal, container)
        splitter.setChildrenCollapsible(False)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(BodyLabel(self.tr("My Teams")))

        self.preset_list = ListWidget(left)
        self.preset_list.setMinimumWidth(210)
        self.preset_list.setMaximumWidth(300)
        self.preset_list.currentRowChanged.connect(self._preset_selected)
        left_layout.addWidget(self.preset_list, 1)

        self.force_button = PrimaryPushButton(FluentIcon.ACCEPT, self.tr("Force This Team"))
        self.force_button.clicked.connect(self._set_forced)
        self.force_button.setToolTip(self.tr("Always use this team, ignoring auto-match."))
        left_layout.addWidget(self.force_button)

        tool_row_1 = QHBoxLayout()
        self.new_button = PushButton(FluentIcon.ADD, self.tr("New"))
        self.new_button.setToolTip(self.tr("Create a new team preset."))
        self.duplicate_button = PushButton(FluentIcon.COPY, self.tr("Copy"))
        self.duplicate_button.setToolTip(self.tr("Duplicate the current team."))
        self.delete_button = PushButton(FluentIcon.DELETE, self.tr("Delete"))
        self.delete_button.setToolTip(self.tr("Delete the current team and its custom code."))
        tool_row_1.addWidget(self.new_button)
        tool_row_1.addWidget(self.duplicate_button)
        tool_row_1.addWidget(self.delete_button)
        left_layout.addLayout(tool_row_1)

        tool_row_2 = QHBoxLayout()
        self.import_button = PushButton(FluentIcon.FOLDER, self.tr("Import"))
        self.import_button.setToolTip(self.tr("Import a team preset from a JSON file."))
        self.export_button = PushButton(FluentIcon.SHARE, self.tr("Export"))
        self.export_button.setToolTip(self.tr("Export the current team to a JSON file."))
        self.from_current_button = PushButton(FluentIcon.DOWNLOAD, self.tr("From Config"))
        self.from_current_button.setToolTip(self.tr("Create a team from the current global character config (advanced)."))
        tool_row_2.addWidget(self.import_button)
        tool_row_2.addWidget(self.export_button)
        tool_row_2.addWidget(self.from_current_button)
        left_layout.addLayout(tool_row_2)

        tool_row_3 = QHBoxLayout()
        self.move_up_button = PushButton(FluentIcon.UP, self.tr("Move Up"))
        self.move_up_button.setToolTip(self.tr("Higher teams win when multiple match the in-game team."))
        self.move_down_button = PushButton(FluentIcon.DOWN, self.tr("Move Down"))
        self.move_down_button.setToolTip(self.tr("Lower teams win when multiple match the in-game team."))
        tool_row_3.addWidget(self.move_up_button)
        tool_row_3.addWidget(self.move_down_button)
        tool_row_3.addStretch(1)
        left_layout.addLayout(tool_row_3)
        for button in (self.new_button, self.duplicate_button, self.delete_button,
                       self.import_button, self.export_button, self.from_current_button,
                       self.move_up_button, self.move_down_button):
            button.setFixedHeight(30)
            button.installEventFilter(ToolTipFilter(button))

        self.new_button.clicked.connect(self._new_preset)
        self.duplicate_button.clicked.connect(self._duplicate_preset)
        self.delete_button.clicked.connect(self._delete_preset)
        self.import_button.clicked.connect(self._import_preset)
        self.export_button.clicked.connect(self._export_preset)
        self.from_current_button.clicked.connect(self._create_from_current)
        self.move_up_button.clicked.connect(lambda: self._move_preset(-1))
        self.move_down_button.clicked.connect(lambda: self._move_preset(1))

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)
        self.editor_panel = QWidget(right)
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)
        self.editor_panel.setVisible(False)

        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel(self.tr("Team Name:")))
        self.name_edit = LineEdit(self.editor_panel)
        self.name_edit.setPlaceholderText(self.tr("e.g. 苏格拉塔 1, 今州日常"))
        self.name_edit.textChanged.connect(self._schedule_auto_save)
        name_layout.addWidget(self.name_edit, 1)
        self.auto_match_check = CheckBox(self.tr("Auto match in-game team"), self.editor_panel)
        self.auto_match_check.setToolTip(self.tr(
            "This team is auto-selected when its characters match the in-game team."))
        self.auto_match_check.setChecked(True)
        self.auto_match_check.toggled.connect(self._schedule_auto_save)
        name_layout.addWidget(self.auto_match_check)
        editor_layout.addLayout(name_layout)

        for index in range(MAX_SLOTS):
            editor = _SlotEditor(self, index)
            editor.char_combo.addItem("", None, "")
            for display, class_name in self.char_options:
                editor.char_combo.addItem(display, None, class_name)
            self.slot_editors.append(editor)
            editor_layout.addWidget(editor)

        editor_layout.addStretch(1)

        bottom_layout = QHBoxLayout()
        self.status_label = BodyLabel("", self.editor_panel)
        self.status_label.setStyleSheet("color:rgba(140,140,140,0.9);")
        bottom_layout.addWidget(self.status_label, 1)
        editor_layout.addLayout(bottom_layout)

        self.editor_scroll = SingleDirectionScrollArea(right)
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setFrameShape(QFrame.NoFrame)
        self.editor_scroll.enableTransparentBackground()
        self.editor_scroll.setWidget(self.editor_panel)
        self.editor_panel.setVisible(False)
        right_layout.addWidget(self.editor_scroll)

        self.empty_card = SimpleCardWidget(right)
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setContentsMargins(28, 32, 28, 32)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignHCenter)
        self.empty_title = BodyLabel(self.tr("No teams yet"), self.empty_card)
        self.empty_title.setStyleSheet("font-size:17px;font-weight:600;")
        self.empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        empty_hint = BodyLabel(self.tr("Create a team to save a character lineup and switch between lineups with one click."), self.empty_card)
        empty_hint.setWordWrap(True)
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_hint.setStyleSheet("color:rgba(140,140,140,0.9);")
        empty_layout.addWidget(empty_hint)
        empty_button = PrimaryPushButton(FluentIcon.ADD, self.tr("Create My First Team"), self.empty_card)
        empty_button.clicked.connect(self._new_preset)
        empty_layout.addWidget(empty_button, 0, Qt.AlignHCenter)
        right_layout.addWidget(self.empty_card)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, 1)
        self.add_widget(container, stretch=1)

        self._refresh_preset_list()

    @property
    def name(self):
        return self.tr("Team Presets")

    @property
    def icon(self):
        return FluentIcon.PEOPLE

    # ---------- char options ----------

    def _build_char_classes(self):
        classes = {}
        for info in char_dict.values():
            cls = info.get("cls")
            if cls is not None:
                classes.setdefault(cls.__name__, cls)
        return classes

    def _build_char_options(self):
        options = []
        for name in sorted(self.char_class_by_name):
            options.append((self._display_char_name(name), name))
        return options

    def _display_char_name(self, class_name):
        return self.tr(CHARACTER_DISPLAY_NAMES.get(class_name, class_name))

    # ---------- preset list ----------

    def _refresh_preset_list(self, selected_id=None):
        presets = TeamPresetStore.list_presets()
        selected_name = selected_id or (self.current_preset.id if self.current_preset else None)
        self.suppress_selection_guard = True
        try:
            self.preset_list.clear()
            selected_row = 0
            active = TeamPresetStore.get_forced_name()
            for row, preset in enumerate(presets):
                label = f"{'✓ ' if preset.id == active else ''}{preset.name or preset.id}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, preset.id)
                self.preset_list.addItem(item)
                if preset.id == selected_name:
                    selected_row = row
            self.preset_list.blockSignals(True)
            self.preset_list.setCurrentRow(min(selected_row, self.preset_list.count() - 1))
            self.preset_list.blockSignals(False)
        finally:
            self.suppress_selection_guard = False
        if self.current_preset is None and self.preset_list.count() > 0:
            preset = TeamPresetStore.get_preset(self.preset_list.item(0).data(Qt.UserRole))
            if preset is not None:
                self.current_preset = preset
                self.current_row = 0
                self._load_preset_into_widgets()
        self._preset_loaded_selection(selected_name)
        self._update_banner()

    def _preset_loaded_selection(self, selected_id):
        has_any = self.preset_list.count() > 0
        self.empty_card.setVisible(not has_any)
        self.editor_panel.setVisible(has_any)

    def _preset_selected(self, row):
        if self.suppress_selection_guard:
            return
        if self._invalid_json_block():
            self.suppress_selection_guard = True
            self.preset_list.setCurrentRow(self.current_row)
            self.suppress_selection_guard = False
            return
        item = self.preset_list.item(row)
        if item is None:
            return
        preset = TeamPresetStore.get_preset(item.data(Qt.UserRole))
        if preset is None:
            return
        self.current_preset = preset
        self.current_row = row
        self._load_preset_into_widgets()

    def _load_preset_into_widgets(self):
        preset = self.current_preset
        self.name_edit.setText(preset.name)
        self.auto_match_check.setChecked(preset.auto_match)
        slots = list(preset.slots) + [None] * (MAX_SLOTS - len(preset.slots))
        for editor, slot in zip(self.slot_editors, slots):
            editor.load_slot(slot)
        self._update_banner()
        self._update_force_state()
        self.status_label.setText(self.tr("Auto saved"))

    def _update_force_state(self):
        forced = TeamPresetStore.get_forced_name()
        is_forced = self.current_preset is not None and self.current_preset.id == forced
        self.force_button.setText(self.tr("Unforce This Team") if is_forced else self.tr("Force This Team"))

    def _update_banner(self):
        detected = TeamPresetStore.get_last_detected_team()
        roles = ' · '.join(self._display_char_name(c) for c in detected)
        forced_preset = TeamPresetStore.get_forced_preset()
        if forced_preset is not None:
            name = forced_preset.name or forced_preset.id
            if roles:
                text = self.tr("Forced team: {name} · {roles}").format(name=name, roles=roles)
            else:
                text = self.tr("Forced team: {name}").format(name=name)
            self._set_badge(True, text)
            return
        auto_matched = TeamPresetStore.get_last_auto_match()
        if auto_matched is not None:
            name = auto_matched.name or auto_matched.id
            if roles:
                text = self.tr("Auto-matched: {name} · {roles}").format(name=name, roles=roles)
            else:
                text = self.tr("Auto-matched: {name}").format(name=name)
            self._set_badge(True, text)
            return
        if roles:
            self._set_badge(False, self.tr(
                "No preset matches: {roles} - using global config").format(roles=roles))
            return
        self._set_badge(False, self.tr(
            "Auto-match on - tasks use the preset matching your in-game team."))

    def _set_badge(self, highlighted, text):
        if highlighted:
            self.active_badge.setStyleSheet(
                "QFrame{background:rgba(76,195,138,0.22);border:1px solid #4cc38a;border-radius:15px;}")
            self.active_badge_text.setStyleSheet("color:#2fa86f;font-weight:600;")
        else:
            self.active_badge.setStyleSheet(
                "QFrame{background:rgba(140,140,140,0.12);border:1px solid rgba(140,140,140,0.35);border-radius:15px;}")
            self.active_badge_text.setStyleSheet("color:rgba(140,140,140,0.95);")
        self.active_badge_text.setText(text)

    # ---------- auto save ----------

    def _schedule_auto_save(self, *_):
        if self.current_preset is None:
            return
        if not self._auto_save_timer.isActive():
            self.status_label.setText(self.tr("Editing…"))
        self._auto_save_timer.start()

    def _auto_save(self):
        if self.current_preset is None:
            return
        try:
            pending = self._preset_from_widgets()
        except ValueError as e:
            self.status_label.setText(self.tr("Not saved: {error}").format(error=e))
            return
        try:
            TeamPresetStore.save_preset(pending)
        except Exception as e:
            self.logger.error(f"save team preset failed: {e}")
            self.status_label.setText(self.tr("Save failed: {error}").format(error=e))
            return
        name_changed = pending.name != self.current_preset.name
        self.current_preset = pending
        if name_changed:
            item = self.preset_list.item(self.current_row)
            if item is not None:
                active = TeamPresetStore.get_forced_name()
                prefix = "✓ " if pending.id == active else ""
                item.setText(f"{prefix}{pending.name or pending.id}")
        self.status_label.setText(self.tr("Auto saved"))

    def _invalid_json_block(self):
        if self.current_preset is None:
            return False
        try:
            self._preset_from_widgets()
            return False
        except ValueError as e:
            show_info_bar(self.window(), str(e), title=self.tr("Not Saved"), error=True)
            return True

    def _preset_from_widgets(self):
        if self.current_preset is None:
            return None
        slots = []
        for editor in self.slot_editors:
            slots.append(editor.to_slot())
        return TeamPreset(
            id=self.current_preset.id,
            name=self.name_edit.text().strip() or self.current_preset.name,
            note=self.current_preset.note,
            created_from=self.current_preset.created_from,
            auto_match=self.auto_match_check.isChecked(),
            slots=slots,
        )

    # ---------- buttons ----------

    def _new_preset(self):
        count = len(TeamPresetStore.list_presets())
        default_name = self.tr("Team {number}").format(number=count + 1)
        name, ok = QInputDialog.getText(self, self.tr("New Team Preset"),
                                        self.tr("Team name:"), text=default_name)
        if not ok or not name.strip():
            return
        name = name.strip()
        new_id = TeamPresetStore.generate_id(name)
        TeamPresetStore.add_preset(TeamPreset(id=new_id, name=name, note=""))
        self._refresh_preset_list(new_id)
        self.current_preset = TeamPresetStore.get_preset(new_id)
        self.current_row = self._row_of_preset(new_id)
        self._load_preset_into_widgets()

    def _row_of_preset(self, preset_id):
        for row in range(self.preset_list.count()):
            item = self.preset_list.item(row)
            if item is not None and item.data(Qt.UserRole) == preset_id:
                return row
        return 0

    def _duplicate_preset(self):
        if self.current_preset is None:
            return
        duplicated = TeamPresetStore.duplicate_preset(self.current_preset.id)
        self._refresh_preset_list(duplicated.id)
        self.current_preset = TeamPresetStore.get_preset(duplicated.id)
        self.current_row = self._row_of_preset(duplicated.id)
        self._load_preset_into_widgets()

    def _delete_preset(self):
        if self.current_preset is None:
            return
        box = MessageBox(self.tr("Delete Team Preset"),
                         self.tr("Delete this team preset and its custom code?"),
                         self.window())
        if not box.exec():
            return
        preset_id = self.current_preset.id
        TeamPresetStore.delete_preset(preset_id)
        self.current_preset = None
        self._refresh_preset_list()
        remaining = TeamPresetStore.list_presets()
        if remaining:
            self.current_preset = remaining[0]
            self.current_row = 0
            self._load_preset_into_widgets()
        else:
            self._reset_widgets()

    def _create_from_current(self):
        name, ok = QInputDialog.getText(self, self.tr("Create from Current Config"),
                                        self.tr("Team name:"))
        if not ok or not name.strip():
            return
        try:
            preset = TeamPresetStore.create_from_current_config(name.strip())
        except Exception as e:
            self.logger.error(f"create preset from current config failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        self._refresh_preset_list(preset.id)
        self.current_preset = TeamPresetStore.get_preset(preset.id)
        self.current_row = self._row_of_preset(preset.id)
        self._load_preset_into_widgets()
        show_info_bar(self.window(), self.tr("Team preset created from current config."),
                      title=self.tr("Success"))

    def _import_preset(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Import Team Preset"), "",
                                              self.tr("JSON Files (*.json);;All Files (*)"))
        if not path:
            return
        try:
            preset = TeamPresetStore.import_preset_from_file(path)
        except Exception as e:
            self.logger.error(f"import team preset failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        self._refresh_preset_list(preset.id)
        self.current_preset = TeamPresetStore.get_preset(preset.id)
        self.current_row = self._row_of_preset(preset.id)
        self._load_preset_into_widgets()
        show_info_bar(self.window(), self.tr("Team preset imported."), title=self.tr("Success"))

    def _export_preset(self):
        if self.current_preset is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export Team Preset"),
                                              f"{self.current_preset.id}.json",
                                              self.tr("JSON Files (*.json);;All Files (*)"))
        if not path:
            return
        try:
            TeamPresetStore.export_preset_to_file(self.current_preset.id, path)
        except Exception as e:
            self.logger.error(f"export team preset failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        show_info_bar(self.window(), self.tr("Team preset exported."), title=self.tr("Success"))

    def _move_preset(self, delta):
        if self.current_preset is None:
            return
        if self._invalid_json_block():
            return
        preset_id = self.current_preset.id
        if TeamPresetStore.move_preset(preset_id, delta):
            self._refresh_preset_list(preset_id)
            self.current_preset = TeamPresetStore.get_preset(preset_id)
            self.current_row = self._row_of_preset(preset_id)
            self._load_preset_into_widgets()

    def _set_forced(self):
        if self.current_preset is None:
            return
        if self._invalid_json_block():
            return
        pending = self._preset_from_widgets()
        if pending is not None:
            TeamPresetStore.save_preset(pending)
            self.current_preset = pending
        preset_id = self.current_preset.id
        forced = TeamPresetStore.get_forced_name()
        TeamPresetStore.set_forced("" if forced == preset_id else preset_id)
        self._refresh_preset_list(preset_id)
        self._update_force_state()
        self._update_banner()
        if forced == preset_id:
            show_info_bar(self.window(), self.tr("Team unforced - auto-match is active again."),
                          title=self.tr("Done"))
        else:
            show_info_bar(self.window(), self.tr("Team forced - tasks always use its settings."),
                          title=self.tr("Done"))

    # ---------- misc ----------

    def _reset_widgets(self):
        self.name_edit.setText("")
        self.status_label.setText("")
        self._update_banner()
        self._update_force_state()
        for editor in self.slot_editors:
            editor.reset_widgets()

    def _reload_live_char_code(self, preset_id, char_name):
        if self.executor is None:
            return 0
        base_cls = self.char_class_by_name.get(char_name)
        if base_cls is None:
            return 0
        new_cls = load_custom_char_class_with_preset(base_cls, preset_id)
        reloaded = 0
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(getattr(self.executor, "trigger_tasks", []))
        for task in tasks:
            if getattr(task, "active_preset_name", None) != preset_id:
                continue
            chars = getattr(task, "chars", None)
            if not chars:
                continue
            for index, char in enumerate(chars):
                if char is None or not isinstance(char, base_cls) or type(char) is new_cls:
                    continue
                replacement = new_cls(
                    task,
                    char.index,
                    char_name=char.char_name,
                    confidence=char.confidence,
                    ring_index=char.ring_index,
                    char_type=char.char_type,
                    buff_time=char.buff_time,
                )
                replacement.is_current_char = char.is_current_char
                replacement.has_intro = char.has_intro
                replacement.has_sub_dps_intro = char.has_sub_dps_intro
                replacement.last_switch_time = char.last_switch_time
                replacement.last_switch_in_time = char.last_switch_in_time
                replacement.last_res = char.last_res
                replacement.last_echo = char.last_echo
                replacement.last_liberation = char.last_liberation
                replacement.last_buff_time = char.last_buff_time
                chars[index] = replacement
                reloaded += 1
        return reloaded

    def _refresh_runtime_state(self):
        self._update_banner()
        if self.preset_list.count() > 0:
            current_id = self.current_preset.id if self.current_preset else ""
            forced = TeamPresetStore.get_forced_name()
            item = self.preset_list.item(self.current_row)
            if item is not None and item.data(Qt.UserRole) == current_id:
                prefix = "✓ " if current_id and current_id == forced else ""
                label = self.current_preset.name or self.current_preset.id
                if item.text() != f"{prefix}{label}":
                    item.setText(f"{prefix}{label}")

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_preset_list()
        self._update_banner()
        self._banner_timer.start()

    def hideEvent(self, event):
        self._banner_timer.stop()
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
            self._auto_save()
        super().hideEvent(event)