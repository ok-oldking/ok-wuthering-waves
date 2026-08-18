import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
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
    CHARACTER_DISPLAY_NAMES,
    load_custom_char_class_with_preset,
    read_builtin_char_code,
)
from src.team_preset.TeamLogicLoader import test_run_team_logic
from src.team_preset.TeamPresetStore import (
    FORCE_SCOPE_ONCE, FORCE_SCOPE_PERSIST, FORCE_SCOPE_UNTIL_MATCH,
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
        self.required_check = CheckBox(self.tab.tr("Required"), self.card)
        self.required_check.setToolTip(self.tab.tr(
            "This team only auto-matches when this character is in your team."))
        self.required_check.setChecked(False)
        header.addWidget(self.required_check)
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
        self.required_check.toggled.connect(self.tab._schedule_auto_save)
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
        self.required_check.setEnabled(checked)
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
        self.required_check.setChecked(bool(slot and slot.required))
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
            required=self.required_check.isChecked(),
        )

    def reset_widgets(self):
        self.char_combo.blockSignals(True)
        self._set_combo_to("")
        self.char_combo.blockSignals(False)
        self.enabled_check.setChecked(True)
        self.required_check.setChecked(False)
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

        import_button = PushButton(FluentIcon.FOLDER, self.tr("Import .py"), self)
        import_button.setToolTip(self.tr("Import a script file and save it for this character."))
        import_button.clicked.connect(self._import_file)
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
        footer.addWidget(import_button)
        footer.addSpacing(6)
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

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import Script (.py)"), "",
            self.tr("Python Files (*.py);;All Files (*)"))
        if not path:
            return
        try:
            code = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            self.tab.logger.error(f"read script file failed: {e}")
            self._set_status(str(e), error=True)
            return
        try:
            TeamPresetStore.save_custom_code(self.preset.id, self.char_name, code)
        except Exception as e:
            self.tab.logger.error(f"save imported script failed: {e}")
            self._set_status(str(e), error=True)
            return
        self.code_editor.setPlainText(code)
        self.clean_code = code
        self.code_has_unsaved_changes = False
        self._refresh_title()
        self._set_status(self.tr("Imported from file and saved"))
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


_TEAM_LOGIC_API_REF = '''队伍逻辑(BaseTeamCombat)API 速查
================================
子类实现 perform() 即可;每 tick 调用一次,用 self.* 实例属性跨 tick 记状态。

基础:
  self.task            任务对象(截图 / 按键 / 日志等)
  self.chars           [0..2] 三个角色对象(未配置的槽位为 None)
  self.char(i)         第 i 个角色对象(0 基),越界返回 None
  self.current_char    当前在场角色
  self.current_index   当前在场槽位(0 基),无人时 None
  self.is_current(i)   i 槽是否在场

切换:
  self.switch_to(i)                直接切换到 i 槽(自带超时与状态更新)
  self.switch_next_char(i)         让 i 槽按优先级选择下一个角色切换
  self.switch_out(i, con_full=)    切出(con_full=True 表示协奏满切)
  self.wait_intro(i, **kw)         等待入场技
  self.wait_down(i, click=True)    等待被击倒后的起身
  self.next_frame()                推进一帧并刷新状态(循环里必须调用)

技能/动作(i 是 0 基槽位):
  self.click(i)               普攻
  self.click_resonance(i)     共鸣技能
  self.click_liberation(i)    共鸣解放
  self.click_echo(i)          声骸
  self.heavy_click_forte(i)   长按重击/共鸣回路
  self.use_tool_box(i)        工具盒

状态查询(i 是 0 基槽位):
  self.liberation_available(i=None)  共鸣解放就绪(默认当前在场角色)
  self.resonance_available(i)        共鸣技能就绪
  self.echo_available(i)             声骸就绪
  self.con_percent(i=None)           协奏值 0~1(仅在场角色可测)
  self.con_full(i=None)              协奏值是否已满(仅在场角色)
  self.cd_remaining(i, box_name)     剩余冷却秒(box_name: resonance/echo/liberation)
  self.is_available(i, percent, box_name)  按百分比判断可用
  self.has_cd(i, box_name)           是否在冷却
  self.has_buff(i) / self.has_all_buff(i)  增益状态
  self.char_is(i, "Rover")           槽位是否是指定角色

其他:
  self.check_combat()   不在战斗时抛异常(任务自动兜底)
  self.sleep(sec, check_combat=)  等待(sec 秒)
  self.log_info / log_debug / log_error(msg)  日志
'''

_TEAM_LOGIC_EXAMPLE = '''class MyTeamLogic(BaseTeamCombat):
    """示例逻辑:谁在场看谁,技能好了就放,协奏值满就切人。"""

    def perform(self):
        me = self.current_char              # 当前在场角色
        if me is None:
            return
        i = me.index
        if self.liberation_available(i):    # 共鸣解放就绪
            self.click_liberation(i)
            return
        if self.echo_available(i):          # 声骸就绪
            self.click_echo(i)
        if self.resonance_available(i):     # 共鸣技能就绪
            self.click_resonance(i)
            return
        if self.con_full(i):                # 协奏值满,切走
            self.switch_next_char(i)
            return
        self.click(i)                       # 普攻
'''


class _TeamLogicDialog(QDialog):
    """Full-window editor for a preset's team-level combat logic."""

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.preset = tab.current_preset
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
        self.source_label.setWordWrap(True)

        self.status_label = BodyLabel("", self)

        import_button = PushButton(FluentIcon.FOLDER, self.tr("Import .py"), self)
        import_button.setToolTip(self.tr("Import a script file and save it as this team's logic."))
        import_button.clicked.connect(self._import_file)
        api_button = PushButton(self.tr("API Quick Ref"), self)
        api_button.setToolTip(self.tr("Show available team logic API (Chinese)."))
        api_button.clicked.connect(self._show_api_ref)
        example_button = PushButton(self.tr("Insert Example"), self)
        example_button.clicked.connect(self._insert_example)
        test_button = PushButton(self.tr("Test Run"), self)
        test_button.setToolTip(self.tr(
            "Run the logic in a safe simulator without fighting or clicking."))
        test_button.clicked.connect(self._test_run)
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
        footer.addWidget(import_button)
        footer.addSpacing(6)
        footer.addWidget(api_button)
        footer.addSpacing(6)
        footer.addWidget(example_button)
        footer.addSpacing(6)
        footer.addWidget(test_button)
        footer.addSpacing(6)
        footer.addWidget(reset_button)
        footer.addSpacing(6)
        footer.addWidget(save_button)
        footer.addWidget(close_button)
        layout.addLayout(footer)

        self._load_code()

    def _load_code(self):
        code = TeamPresetStore.read_team_code(self.preset.id)
        if code is None:
            self.source_label.setText(self.tr(
                "No team logic yet - each character fights on its own. "
                "Write a BaseTeamCombat subclass to take full control of the team."))
        else:
            self.source_label.setText(self.tr(
                "This team logic fully replaces the characters' own combat logic."))
        self.code_editor.setPlainText(code or "")
        self.clean_code = self.code_editor.toPlainText()
        self.code_has_unsaved_changes = False
        preset_name = self.preset.name if self.preset and self.preset.name else ""
        self.base_title = self.tr("Team Logic")
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

    def _insert_example(self):
        self.code_editor.setPlainText(_TEAM_LOGIC_EXAMPLE)
        self._set_status(self.tr("Example inserted - edit and save"))

    def _test_run(self):
        if self.code_editor.toPlainText() != self.clean_code:
            self._set_status(self.tr("Save code before testing"), error=True)
            return
        frames, ok = QInputDialog.getInt(
            self, self.tr("Test Run"), self.tr("Frames to simulate:"), 120, 1, 10000, 1)
        if not ok:
            return
        ok, message = test_run_team_logic(self.preset.id, frames=frames)
        self._set_status(message.split("\n")[0], error=not ok)
        if not ok and "\n" in message:
            dialog = QDialog(self)
            dialog.setWindowTitle(self.tr("Test Run Failed"))
            dialog.setMinimumSize(520, 320)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(16, 16, 16, 16)
            editor = CodeEditor(dialog)
            editor.setReadOnly(True)
            editor.setLineWrapMode(PlainTextEdit.NoWrap)
            font = editor.font()
            font.setFamily("Consolas")
            font.setPointSize(10)
            editor.setFont(font)
            editor.setPlainText(message)
            close_button = PrimaryPushButton(self.tr("Close"), dialog)
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(editor, 1)
            button_row = QHBoxLayout()
            button_row.addStretch(1)
            button_row.addWidget(close_button)
            layout.addLayout(button_row)
            dialog.exec()

    def _show_api_ref(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Team Logic API Quick Reference"))
        dialog.setMinimumSize(560, 420)
        dialog.resize(680, 560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        editor = CodeEditor(dialog)
        editor.setReadOnly(True)
        editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = editor.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        editor.setFont(font)
        editor.setPlainText(_TEAM_LOGIC_API_REF)
        close_button = PrimaryPushButton(self.tr("Close"), dialog)
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(editor, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)
        dialog.exec()

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import Script (.py)"), "",
            self.tr("Python Files (*.py);;All Files (*)"))
        if not path:
            return
        try:
            code = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            self.tab.logger.error(f"read script file failed: {e}")
            self._set_status(str(e), error=True)
            return
        try:
            TeamPresetStore.save_team_code(self.preset.id, code)
        except Exception as e:
            self.tab.logger.error(f"save imported team logic failed: {e}")
            self._set_status(str(e), error=True)
            return
        self.code_editor.setPlainText(code)
        self.clean_code = code
        self.code_has_unsaved_changes = False
        self._refresh_title()
        self._set_status(self.tr("Imported from file and saved"))
        self.tab._update_team_logic_button()
        reloaded = self.tab._reload_live_team_logic(self.preset.id)
        if reloaded:
            self._set_status(self.tr("Imported - live-reloaded into {n} running task(s)").format(
                n=reloaded))

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color:#cf4d4d;" if error else "color:#2fa86f;")

    def _save_code(self):
        code = self.code_editor.toPlainText()
        try:
            TeamPresetStore.save_team_code(self.preset.id, code)
        except Exception as e:
            self.tab.logger.error(f"save team logic failed: {e}")
            self._set_status(str(e), error=True)
            return
        self.clean_code = code
        self.code_has_unsaved_changes = False
        self._refresh_title()
        self._set_status(self.tr("Code saved"))
        self.tab._update_team_logic_button()
        reloaded = self.tab._reload_live_team_logic(self.preset.id)
        if reloaded:
            self._set_status(self.tr("Code saved - live-reloaded into {n} running task(s)").format(
                n=reloaded))

    def _reset_code(self):
        if self.code_has_unsaved_changes:
            box = MessageBox(self.tr("Unsaved Changes"),
                             self.tr("Discard unsaved preset character code changes?"),
                             self)
            if not box.exec():
                return
        TeamPresetStore.remove_team_code(self.preset.id)
        self.code_editor.setPlainText("")
        self.clean_code = ""
        self.code_has_unsaved_changes = False
        self._refresh_title()
        self._set_status(self.tr("Reset to builtin"))
        self.tab._update_team_logic_button()

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

        self.search_edit = LineEdit(left)
        self.search_edit.setPlaceholderText(self.tr("Search teams…"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _: self._refresh_preset_list())
        left_layout.addWidget(self.search_edit)

        self.tag_filter_combo = ComboBox()
        self.tag_filter_combo.setToolTip(self.tr("Filter teams by tag."))
        self.tag_filter_combo.addItem(self.tr("All tags"), "")
        self.tag_filter_combo.currentIndexChanged.connect(
            lambda _: self._refresh_preset_list())
        left_layout.addWidget(self.tag_filter_combo)

        self.preset_list = ListWidget(left)
        self.preset_list.setMinimumWidth(210)
        self.preset_list.setMaximumWidth(300)
        self.preset_list.currentRowChanged.connect(self._preset_selected)
        left_layout.addWidget(self.preset_list, 1)

        self.force_button = PrimaryPushButton(FluentIcon.ACCEPT, self.tr("Force This Team"))
        self.force_button.clicked.connect(self._set_forced)
        self.force_button.setToolTip(self.tr("Always use this team, ignoring auto-match."))
        force_row = QHBoxLayout()
        force_row.addWidget(self.force_button, 1)
        self.force_scope_combo = ComboBox()
        self._force_scopes = [
            (FORCE_SCOPE_PERSIST, self.tr("Persistent")),
            (FORCE_SCOPE_ONCE, self.tr("Once")),
            (FORCE_SCOPE_UNTIL_MATCH, self.tr("Until match")),
        ]
        for scope_key, label in self._force_scopes:
            self.force_scope_combo.addItem(label, scope_key)
        self.force_scope_combo.setToolTip(self.tr(
            "How long the forced team stays forced: persistent, once, or until "
            "auto-match finds another team."))
        self.force_scope_combo.currentIndexChanged.connect(self._force_scope_changed)
        force_row.addWidget(self.force_scope_combo)
        left_layout.addLayout(force_row)

        self.only_full_check = CheckBox(self.tr("Only full match"), left)
        self.only_full_check.setToolTip(self.tr(
            "Only auto-match teams whose every enabled character is in the in-game team."))
        self.only_full_check.toggled.connect(self._only_full_changed)
        left_layout.addWidget(self.only_full_check)

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
        self.import_button.setToolTip(self.tr("Import teams from a JSON file (single or batch)."))
        self.export_button = PushButton(FluentIcon.SHARE, self.tr("Export"))
        self.export_button.setToolTip(self.tr("Export the current team to a JSON file."))
        self.from_team_button = PushButton(FluentIcon.PEOPLE, self.tr("From Team"))
        self.from_team_button.setToolTip(self.tr("Create a team from the currently detected in-game team."))
        tool_row_2.addWidget(self.import_button)
        tool_row_2.addWidget(self.export_button)
        tool_row_2.addWidget(self.from_team_button)
        left_layout.addLayout(tool_row_2)

        tool_row_2b = QHBoxLayout()
        self.from_current_button = PushButton(FluentIcon.DOWNLOAD, self.tr("From Config"))
        self.from_current_button.setToolTip(self.tr("Create a team from the current global character config (advanced)."))
        self.template_button = PushButton(FluentIcon.BOOK_SHELF, self.tr("From Template"))
        self.template_button.setToolTip(self.tr(
            "Create a new team from a built-in template with ready-to-run scripts."))
        self.template_button.clicked.connect(self._from_template)
        self.from_url_button = PushButton(FluentIcon.LINK, self.tr("From URL"))
        self.from_url_button.setToolTip(self.tr("Install a team preset from a JSON URL."))
        tool_row_2b.addWidget(self.from_current_button)
        tool_row_2b.addWidget(self.template_button)
        tool_row_2b.addWidget(self.from_url_button)
        left_layout.addLayout(tool_row_2b)

        tool_row_3 = QHBoxLayout()
        self.export_all_button = PushButton(FluentIcon.EXPORT, self.tr("Export All"))
        self.export_all_button.setToolTip(self.tr("Export all teams to one JSON file."))
        self.move_up_button = PushButton(FluentIcon.UP, self.tr("Move Up"))
        self.move_up_button.setToolTip(self.tr("Higher teams win when multiple match the in-game team."))
        self.move_down_button = PushButton(FluentIcon.DOWN, self.tr("Move Down"))
        self.move_down_button.setToolTip(self.tr("Lower teams win when multiple match the in-game team."))
        tool_row_3.addWidget(self.export_all_button)
        tool_row_3.addWidget(self.move_up_button)
        tool_row_3.addWidget(self.move_down_button)
        tool_row_3.addStretch(1)
        left_layout.addLayout(tool_row_3)

        tool_row_4 = QHBoxLayout()
        self.backup_button = PushButton(FluentIcon.SAVE, self.tr("Backup"))
        self.backup_button.setToolTip(self.tr("Back up all teams (with custom code) to a zip file."))
        self.restore_button = PushButton(FluentIcon.FOLDER_ADD, self.tr("Restore"))
        self.restore_button.setToolTip(self.tr("Restore teams from a backup zip file."))
        self.export_template_button = PushButton(FluentIcon.ZIP_FOLDER, self.tr("Template"))
        self.export_template_button.setToolTip(self.tr(
            "Export the current team as a built-in template folder for sharing."))
        tool_row_4.addWidget(self.backup_button)
        tool_row_4.addWidget(self.restore_button)
        tool_row_4.addWidget(self.export_template_button)
        tool_row_4.addStretch(1)
        left_layout.addLayout(tool_row_4)
        for button in (self.new_button, self.duplicate_button, self.delete_button,
                       self.import_button, self.export_button, self.from_team_button,
                       self.from_current_button, self.template_button,
                       self.from_url_button, self.export_all_button,
                       self.move_up_button, self.move_down_button,
                       self.backup_button, self.restore_button,
                       self.export_template_button):
            button.setFixedHeight(30)
            button.installEventFilter(ToolTipFilter(button))

        self.new_button.clicked.connect(self._new_preset)
        self.duplicate_button.clicked.connect(self._duplicate_preset)
        self.delete_button.clicked.connect(self._delete_preset)
        self.import_button.clicked.connect(self._import_preset)
        self.export_button.clicked.connect(self._export_preset)
        self.from_team_button.clicked.connect(self._create_from_detected)
        self.from_current_button.clicked.connect(self._create_from_current)
        self.from_url_button.clicked.connect(self._install_from_url)
        self.export_all_button.clicked.connect(self._export_all)
        self.backup_button.clicked.connect(self._backup_zip)
        self.restore_button.clicked.connect(self._restore_zip)
        self.export_template_button.clicked.connect(self._export_template_folder)
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

        self.description_edit = LineEdit(self.editor_panel)
        self.description_edit.setPlaceholderText(
            self.tr("Description (optional) - shown when sharing as a template or file"))
        self.description_edit.textChanged.connect(self._schedule_auto_save)
        editor_layout.addWidget(self.description_edit)

        self.tags_edit = LineEdit(self.editor_panel)
        self.tags_edit.setPlaceholderText(
            self.tr("Tags (optional, comma separated) - e.g. 深渊, 大世界"))
        self.tags_edit.textChanged.connect(self._schedule_auto_save)
        editor_layout.addWidget(self.tags_edit)

        self.team_logic_button = PushButton(FluentIcon.CODE, self.tr("Team Logic"), self.editor_panel)
        self.team_logic_button.setToolTip(self.tr(
            "Team-level combat logic - takes full control when the team is matched or forced."))
        self.team_logic_button.clicked.connect(self._open_team_logic_dialog)
        editor_layout.addWidget(self.team_logic_button)

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
        self.diagnose_button = PushButton(FluentIcon.SEARCH, self.tr("Match Log"),
                                          self.editor_panel)
        self.diagnose_button.setToolTip(self.tr(
            "Show why the current team was (or was not) auto-matched last time."))
        self.diagnose_button.clicked.connect(self._show_match_diagnostics)
        self.diagnose_button.setFixedHeight(28)
        bottom_layout.addWidget(self.diagnose_button)
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

        self.only_full_check.setChecked(TeamPresetStore.get_only_full_match())
        self._sync_force_scope_combo()
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
        all_presets = TeamPresetStore.list_presets()
        all_tags = sorted({t for p in all_presets for t in (p.tags or [])})
        current_tag = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex()) or ""
        current_items = [self.tag_filter_combo.itemData(i)
                         for i in range(self.tag_filter_combo.count())]
        if current_items != [""] + all_tags:
            self.tag_filter_combo.blockSignals(True)
            self.tag_filter_combo.clear()
            self.tag_filter_combo.addItem(self.tr("All tags"), "")
            for tag in all_tags:
                self.tag_filter_combo.addItem(tag, tag)
            index = self.tag_filter_combo.findData(current_tag)
            self.tag_filter_combo.setCurrentIndex(index if index >= 0 else 0)
            self.tag_filter_combo.blockSignals(False)
        tag_query = current_tag
        presets = all_presets
        if tag_query:
            presets = [p for p in presets if tag_query in (p.tags or [])]
        query = self.search_edit.text().strip().lower()
        selected_name = selected_id or (self.current_preset.id if self.current_preset else None)
        detected = set(TeamPresetStore.get_last_detected_team() or [])
        self.suppress_selection_guard = True
        try:
            self.preset_list.clear()
            selected_row = 0
            active = TeamPresetStore.get_forced_name()
            for row, preset in enumerate(presets):
                label = f"{preset.name or preset.id}"
                if query:
                    haystack = " ".join([
                        label.lower(), preset.note.lower(), preset.description.lower(),
                        " ".join(preset.tags).lower(),
                        " ".join(slot.char for slot in preset.slots)])
                    if query not in haystack:
                        continue
                error = TeamPresetStore.get_preset_error(preset.id)
                stats = TeamPresetStore.get_preset_stats(preset.id)
                full_hit, partial, note = self._preset_hit_info(preset, detected)
                suffix = ""
                if preset.id == active:
                    suffix = " ✓"
                elif full_hit:
                    suffix = f" · {self.tr('full match')}"
                elif partial:
                    suffix = f" · {note}"
                elif detected and note:
                    suffix = f" · {note}"
                if error:
                    suffix += " ⚠"
                item = QListWidgetItem(f"{label}{suffix}")
                item.setData(Qt.UserRole, preset.id)
                if error:
                    item.setForeground(QColor("#cf4d4d"))
                elif full_hit:
                    item.setForeground(QColor("#4cc38a"))
                elif preset.id == active:
                    item.setForeground(QColor("#6cb8ff"))
                tip_lines = []
                if stats.get("uses"):
                    tip_lines.append(self.tr("Used {n} times").format(n=stats["uses"]))
                if stats.get("successes") or stats.get("fails"):
                    wins = stats.get("successes", 0)
                    total = wins + stats.get("fails", 0)
                    tip_lines.append(self.tr("Combat: {wins}/{total} won").format(
                        wins=wins, total=total))
                if stats.get("errors"):
                    tip_lines.append(self.tr("{n} errors").format(n=stats["errors"]))
                if error:
                    tip_lines.append(str(error.get("message", ""))[:80])
                if preset.description:
                    tip_lines.append(preset.description)
                if tip_lines:
                    item.setToolTip("\n".join(tip_lines))
                self.preset_list.addItem(item)
                if preset.id == selected_name:
                    selected_row = self.preset_list.count() - 1
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

    def _preset_hit_info(self, preset, detected):
        """返回 (full_hit, partial, note):基于检测队伍的角色命中标注。"""
        if not detected:
            return False, False, ""
        score, missing_required, hits = TeamPresetStore._preset_match(preset, detected)
        if score <= 0:
            if missing_required:
                missing = " · ".join(self._display_char_name(c) for c in missing_required)
                return False, False, self.tr("needs {chars}").format(chars=missing)
            return False, False, ""
        enabled = [slot for slot in preset.slots if slot.enabled and slot.char]
        full = len(hits) == len(enabled)
        note = self.tr("matched {hits}/{total}").format(hits=len(hits), total=len(enabled))
        return full, not full, note

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
        self.description_edit.setText(preset.description)
        self.tags_edit.setText(", ".join(preset.tags))
        self.auto_match_check.setChecked(preset.auto_match)
        slots = list(preset.slots) + [None] * (MAX_SLOTS - len(preset.slots))
        for editor, slot in zip(self.slot_editors, slots):
            editor.load_slot(slot)
        self._update_team_logic_button()
        self._update_banner()
        self._update_force_state()
        stats = TeamPresetStore.get_preset_stats(preset.id)
        status_parts = []
        if stats.get("uses"):
            status_parts.append(self.tr("Used {n} times").format(n=stats["uses"]))
        if stats.get("successes") or stats.get("fails"):
            wins = stats.get("successes", 0)
            total = wins + stats.get("fails", 0)
            status_parts.append(self.tr("Combat: {wins}/{total} won").format(
                wins=wins, total=total))
        if status_parts:
            self.status_label.setText(" · ".join(status_parts))
        else:
            self.status_label.setText(self.tr("Auto saved"))

    def _open_team_logic_dialog(self):
        if self.current_preset is None:
            return
        _TeamLogicDialog(self, self.window()).exec()

    def _update_team_logic_button(self):
        has = self.current_preset is not None and TeamPresetStore.has_team_code(self.current_preset.id)
        self.team_logic_button.setText(
            self.tr("Team Logic: On") if has else self.tr("Team Logic"))
        self.team_logic_button.setStyleSheet(
            "QPushButton{color:#2fa86f;border-color:#4cc38a;}" if has else "")

    def _update_force_state(self):
        forced = TeamPresetStore.get_forced_name()
        is_forced = self.current_preset is not None and self.current_preset.id == forced
        self.force_button.setText(self.tr("Unforce This Team") if is_forced else self.tr("Force This Team"))
        self._sync_force_scope_combo()

    def _sync_force_scope_combo(self):
        scope = TeamPresetStore.get_force_scope()
        for i in range(self.force_scope_combo.count()):
            if self.force_scope_combo.itemData(i) == scope:
                self.force_scope_combo.blockSignals(True)
                self.force_scope_combo.setCurrentIndex(i)
                self.force_scope_combo.blockSignals(False)
                return

    def _force_scope_changed(self, index):
        scope = self.force_scope_combo.itemData(index)
        if scope:
            TeamPresetStore.set_force_scope(scope)
            self._update_banner()

    def _only_full_changed(self, checked):
        TeamPresetStore.set_only_full_match(checked)
        self._refresh_preset_list()

    def _update_banner(self):
        error = TeamPresetStore.get_last_team_logic_error()
        if error:
            message = str(error.get("message", ""))[:60]
            self._set_badge(True, self.tr(
                "Team logic error: {msg} - fell back to per-character logic").format(msg=message),
                            error=True)
            return
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
            text = self.tr(
                "No preset matches: {roles} - using global config").format(roles=roles)
            self._set_badge(False, text,
                            tooltip=self._match_attempts_text(
                                TeamPresetStore.get_last_match_attempts()))
            return
        self._set_badge(False, self.tr(
            "Auto-match on - tasks use the preset matching your in-game team."))

    def _match_attempts_text(self, attempts):
        if not attempts:
            return ""
        lines = []
        for attempt in attempts:
            percent = int(round((attempt.get("score") or 0.0) * 100))
            parts = [f"{attempt.get('preset', '')}: {percent}%"]
            missing = attempt.get("missing_required") or []
            if missing:
                parts.append(self.tr("missing {chars}").format(chars=", ".join(missing)))
            lines.append(" · ".join(parts))
        return "\n".join(lines)

    def _set_badge(self, highlighted, text, error=False, tooltip=""):
        if error:
            self.active_badge.setStyleSheet(
                "QFrame{background:rgba(207,77,77,0.22);border:1px solid #cf4d4d;border-radius:15px;}")
            self.active_badge_text.setStyleSheet("color:#cf4d4d;font-weight:600;")
        elif highlighted:
            self.active_badge.setStyleSheet(
                "QFrame{background:rgba(76,195,138,0.22);border:1px solid #4cc38a;border-radius:15px;}")
            self.active_badge_text.setStyleSheet("color:#2fa86f;font-weight:600;")
        else:
            self.active_badge.setStyleSheet(
                "QFrame{background:rgba(140,140,140,0.12);border:1px solid rgba(140,140,140,0.35);border-radius:15px;}")
            self.active_badge_text.setStyleSheet("color:rgba(140,140,140,0.95);")
        self.active_badge_text.setText(text)
        if tooltip:
            self.active_badge.setToolTip(tooltip)
        else:
            self.active_badge.setToolTip("")

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
                active = TeamPresetStore.get_forced_name() == pending.id
                item.setText(f"{pending.name or pending.id}{' ✓' if active else ''}")
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
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        return TeamPreset(
            id=self.current_preset.id,
            name=self.name_edit.text().strip() or self.current_preset.name,
            note=self.current_preset.note,
            created_from=self.current_preset.created_from,
            auto_match=self.auto_match_check.isChecked(),
            description=self.description_edit.text().strip(),
            tags=tags,
            slots=slots,
        )

    def _from_template(self):
        templates = TeamPresetStore.list_builtin_templates()
        if not templates:
            show_info_bar(self.window(), self.tr("No built-in templates available."),
                          title=self.tr("Info"))
            return
        items = [f"{t['name']} - {t['description']}" if t["description"] else t["name"]
                 for t in templates]
        choice, ok = QInputDialog.getItem(
            self, self.tr("Create from Template"),
            self.tr("Choose a template:"), items, 0, False)
        if not ok or not choice:
            return
        template = templates[items.index(choice)]
        try:
            preset = TeamPresetStore.install_builtin_template(template["folder"])
        except Exception as e:
            self.logger.error(f"install builtin template failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        self._refresh_preset_list(preset.id)
        self.current_preset = TeamPresetStore.get_preset(preset.id)
        self.current_row = self._row_of_preset(preset.id)
        self._load_preset_into_widgets()
        show_info_bar(self.window(), self.tr("Template installed: {name}").format(
            name=preset.name), title=self.tr("Success"))

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
        is_forced = TeamPresetStore.get_forced_name() == self.current_preset.id
        question = self.tr("Delete this team preset and its custom code?")
        if is_forced:
            question = self.tr(
                "This team is currently FORCED - it will stop being applied "
                "after deletion. Delete anyway?")
        box = MessageBox(self.tr("Delete Team Preset"), question, self.window())
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
            imported, warnings = TeamPresetStore.import_presets_from_file(path)
        except Exception as e:
            self.logger.error(f"import team presets failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        if not imported:
            return
        self._refresh_preset_list(imported[0].id)
        self.current_preset = TeamPresetStore.get_preset(imported[0].id)
        self.current_row = self._row_of_preset(imported[0].id)
        self._load_preset_into_widgets()
        message = self.tr("Imported {n} teams.").format(n=len(imported))
        for warning in warnings:
            chars = ", ".join(warning["unknown_chars"])
            message += " " + self.tr("{name}: unknown characters {chars} "
                                     "(from a newer version?)").format(
                name=warning["preset"], chars=chars)
        show_info_bar(self.window(), message,
                      title=self.tr("Success") if not warnings else self.tr("Warning"),
                      error=bool(warnings))

    def _export_all(self):
        presets = TeamPresetStore.list_presets()
        if not presets:
            show_info_bar(self.window(), self.tr("No teams to export."),
                          title=self.tr("Info"))
            return
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export All Teams"),
                                              "teams.json",
                                              self.tr("JSON Files (*.json);;All Files (*)"))
        if not path:
            return
        try:
            TeamPresetStore.export_presets_to_file([p.id for p in presets], path)
        except Exception as e:
            self.logger.error(f"export all team presets failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        show_info_bar(self.window(),
                      self.tr("Exported {n} teams.").format(n=len(presets)),
                      title=self.tr("Success"))

    def _backup_zip(self):
        presets = TeamPresetStore.list_presets()
        if not presets:
            show_info_bar(self.window(), self.tr("No teams to back up."),
                          title=self.tr("Info"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Back Up All Teams"), "teams_backup.zip",
            self.tr("ZIP Files (*.zip);;All Files (*)"))
        if not path:
            return
        try:
            TeamPresetStore.backup_presets_to_zip([p.id for p in presets], path)
        except Exception as e:
            self.logger.error(f"backup team presets failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        show_info_bar(self.window(),
                      self.tr("Backed up {n} teams to {path}.").format(
                          n=len(presets), path=path),
                      title=self.tr("Success"))

    def _restore_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Restore Teams from Backup"), "",
            self.tr("ZIP Files (*.zip);;All Files (*)"))
        if not path:
            return
        try:
            imported, warnings = TeamPresetStore.restore_presets_from_zip(path)
        except Exception as e:
            self.logger.error(f"restore team presets failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        if not imported:
            return
        self._refresh_preset_list(imported[0].id)
        self.current_preset = TeamPresetStore.get_preset(imported[0].id)
        self.current_row = self._row_of_preset(imported[0].id)
        self._load_preset_into_widgets()
        message = self.tr("Restored {n} teams.").format(n=len(imported))
        for warning in warnings:
            chars = ", ".join(warning["unknown_chars"])
            message += " " + self.tr("{name}: unknown characters {chars} "
                                     "(from a newer version?)").format(
                name=warning["preset"], chars=chars)
        show_info_bar(self.window(), message,
                      title=self.tr("Success") if not warnings else self.tr("Warning"),
                      error=bool(warnings))

    def _export_template_folder(self):
        if self.current_preset is None:
            return
        preset_id = self.current_preset.id
        folder, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export as Built-in Template"),
            f"{self.current_preset.name}",
            self.tr("Folder Name"))
        if not folder:
            return
        try:
            TeamPresetStore.export_preset_as_template_folder(
                preset_id, Path(folder))
        except Exception as e:
            self.logger.error(f"export template folder failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        show_info_bar(self.window(),
                      self.tr("Template exported to {path} - put it under the "
                              "repo presets/ folder to share.").format(path=folder),
                      title=self.tr("Success"))

    def _show_match_diagnostics(self):
        detected = TeamPresetStore.get_last_detected_team() or []
        lines = []
        roles = " · ".join(self._display_char_name(c) for c in detected)
        lines.append(self.tr("Last detected in-game team: {roles}").format(
            roles=roles or self.tr("(none yet)")))
        forced = TeamPresetStore.get_forced_preset()
        if forced is not None:
            lines.append(self.tr("Forced team: {name} ({scope})").format(
                name=forced.name or forced.id,
                scope=self.force_scope_combo.currentText()))
        else:
            lines.append(self.tr("Forced team: none"))
        auto = TeamPresetStore.get_last_auto_match()
        lines.append(self.tr("Last auto-match: {name}").format(
            name=(auto.name or auto.id) if auto is not None else self.tr("none")))
        lines.append("")
        attempts = TeamPresetStore.get_last_match_attempts()
        if not attempts:
            lines.append(self.tr("No auto-match attempts recorded yet."))
        for attempt in attempts:
            preset_id = attempt.get("preset", "")
            lines.append(f"- {preset_id}")
            if attempt.get("filtered"):
                lines.append("  " + self.tr("skipped: filtered by Only Full Match"))
            else:
                lines.append("  " + self.tr(
                    "score {score}, matched {hits}/{total}, missing required: {missing}").format(
                    score=attempt.get("score", 0),
                    hits=len(attempt.get("hits", [])),
                    total=attempt.get("total", 0) or 1,
                    missing=", ".join(attempt.get("missing_required") or []) or self.tr("none")))
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Match Diagnostics"))
        dialog.setMinimumSize(520, 380)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        editor = CodeEditor(dialog)
        editor.setReadOnly(True)
        editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = editor.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        editor.setPlainText("\n".join(lines))
        close_button = PrimaryPushButton(self.tr("Close"), dialog)
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(editor, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)
        dialog.exec()

    def _create_from_detected(self):
        detected = TeamPresetStore.get_last_detected_team()
        if not detected:
            show_info_bar(self.window(),
                          self.tr("No in-game team detected yet - run a combat task once."),
                          title=self.tr("Info"))
            return
        default_name = " · ".join(self._display_char_name(c) for c in detected)
        name, ok = QInputDialog.getText(self, self.tr("Create from Detected Team"),
                                        self.tr("Team name:"), text=default_name)
        if not ok or not name.strip():
            return
        try:
            preset = TeamPresetStore.create_from_detected_team(name.strip())
        except Exception as e:
            self.logger.error(f"create preset from detected team failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        self._refresh_preset_list(preset.id)
        self.current_preset = TeamPresetStore.get_preset(preset.id)
        self.current_row = self._row_of_preset(preset.id)
        self._load_preset_into_widgets()
        show_info_bar(self.window(), self.tr("Team preset created from the detected team."),
                      title=self.tr("Success"))

    def _install_from_url(self):
        url, ok = QInputDialog.getText(self, self.tr("Install from URL"),
                                       self.tr("Preset JSON URL:"))
        if not ok or not url.strip():
            return
        try:
            preset = TeamPresetStore.install_preset_from_url(url.strip())
        except Exception as e:
            self.logger.error(f"install preset from url failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        self._refresh_preset_list(preset.id)
        self.current_preset = TeamPresetStore.get_preset(preset.id)
        self.current_row = self._row_of_preset(preset.id)
        self._load_preset_into_widgets()
        show_info_bar(self.window(), self.tr("Team preset installed from URL."),
                      title=self.tr("Success"))

    def _export_preset(self):
        if self.current_preset is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export Team Preset"),
                                              f"{self.current_preset.id}.json",
                                              self.tr("JSON Files (*.json);;All Files (*)"))
        if not path:
            return
        try:
            data = TeamPresetStore.export_preset_to_file(self.current_preset.id, path)
        except Exception as e:
            self.logger.error(f"export team preset failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return
        if data.get("team_code_error"):
            show_info_bar(self.window(),
                          self.tr("Team logic code failed to compile: {error} - "
                                  "it was exported but will not load.")
                          .format(error=str(data["team_code_error"])[:80]),
                          title=self.tr("Warning"))
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
        self.description_edit.setText("")
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

    def _reload_live_team_logic(self, preset_id):
        """把已保存的 team code 热重载到正在运行的匹配/强制任务,返回重载数。"""
        if self.executor is None:
            return 0
        try:
            from src.team_preset.TeamLogicLoader import load_team_logic
        except Exception:
            return 0
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(
            getattr(self.executor, "trigger_tasks", []))
        reloaded = 0
        for task in tasks:
            active_preset = getattr(task, "active_preset", None)
            if active_preset is None or getattr(active_preset, "id", None) != preset_id:
                continue
            if getattr(task, "active_team_logic", None) is None:
                continue
            try:
                cls = load_team_logic(preset_id)
                if cls is None:
                    continue
                task.active_team_logic = cls(task, task.chars)
                reloaded += 1
            except Exception as e:
                self.logger.error(f"live reload team logic failed: {e}")
        return reloaded

    def _refresh_runtime_state(self):
        self._update_banner()
        if self.preset_list.count() > 0:
            current_id = self.current_preset.id if self.current_preset else ""
            forced = TeamPresetStore.get_forced_name()
            item = self.preset_list.item(self.current_row)
            if item is not None and item.data(Qt.UserRole) == current_id:
                suffix = " ✓" if current_id and current_id == forced else ""
                label = f"{self.current_preset.name or self.current_preset.id}{suffix}"
                if item.text() != label:
                    item.setText(label)

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