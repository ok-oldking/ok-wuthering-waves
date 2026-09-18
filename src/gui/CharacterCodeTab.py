import difflib
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import urlopen

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPixmap, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
    QListWidgetItem, QSplitter, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    BodyLabel, ComboBox, FluentIcon, LineEdit, ListWidget, MessageBox, MessageBoxBase,
    PlainTextEdit, PrimaryPushButton, PushButton, SubtitleLabel, TableWidget, TextEdit,
)

from ok import Logger
from ok.gui.tasks.EditTaskTab import CodeEditor
from ok.gui.tasks.PythonHighlighter import PythonHighlighter
from ok.gui.util.app import show_info_bar
from ok.gui.widget.CustomTab import CustomTab
from src.char.CharFactory import apply_team_char_classes, char_dict
from src.char.CustomCharLoader import (
    create_custom_team, delete_custom_team, export_custom_team, get_english_char_name,
    import_custom_team, inspect_team_archive, list_custom_teams, normalize_team,
    read_builtin_char_code, read_team_char_code, save_team_char_code,
)

BASE_CHAR_URL = "https://raw.githubusercontent.com/ok-oldking/ok-wuthering-waves/refs/heads/master/src/char/BaseChar.py"
UPLOAD_TEAM_URL = "https://github.com/ok-oldking/ok-ww-char-code"
WORKSHOP_TEAM_URL = "https://okwwcharcode.ok-script.com/teams/{slug}.json"
WORKSHOP_ARCHIVE_HOSTS = {"okwwcharcode.ok-script.com", "raw.githubusercontent.com"}
logger = Logger.get_logger(__name__)


def translate_ui(message):
    from ok import og
    if og.app:
        return og.app.tr(message)
    return message


class TranslatedDialog(MessageBoxBase):
    def tr(self, message):
        return translate_ui(message)

    def set_dialog_title(self, title):
        self.setWindowTitle(title)
        self.title_label = SubtitleLabel(title, self.widget)
        self.viewLayout.addWidget(self.title_label)

    def add_field(self, label, value):
        label_widget = BodyLabel(label, self.widget)
        value_widget = BodyLabel(str(value), self.widget)
        value_widget.setWordWrap(True)
        self.viewLayout.addWidget(label_widget)
        self.viewLayout.addWidget(value_widget)
        return value_widget


def workshop_team_slug(team):
    names = sorted((
        re.sub(r"[^A-Za-z0-9-]+", "_", get_english_char_name(name)).strip("_")
        for name in normalize_team(team)
    ), key=str.casefold)
    return "_".join(names)


def workshop_team_url(team):
    return WORKSHOP_TEAM_URL.format(slug=quote(workshop_team_slug(team), safe="_-"))


def fetch_workshop_codes(team):
    expected_members = sorted((get_english_char_name(name) for name in normalize_team(team)), key=str.casefold)
    url = workshop_team_url(team)
    logger.info(f"char code workshop request: {url}")
    try:
        with urlopen(url, timeout=15) as response:
            content = response.read(2_000_001)
    except HTTPError as error:
        if error.code == 404:
            return []
        raise
    if len(content) > 2_000_000:
        raise ValueError(translate_ui("Workshop response is too large."))
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(translate_ui("Workshop returned invalid JSON.")) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("codes"), list):
        raise ValueError(translate_ui("Workshop response is invalid."))
    members = payload.get("members")
    if members is not None and sorted(members, key=str.casefold) != expected_members:
        raise ValueError(translate_ui("Workshop returned a different team."))
    codes = [code for code in payload["codes"] if isinstance(code, dict)]
    return sorted(codes, key=lambda code: int(code.get("timestamp") or 0), reverse=True)


def format_workshop_local_time(code):
    modified_at = code.get("modifiedAt")
    try:
        if modified_at:
            value = datetime.fromisoformat(str(modified_at).replace("Z", "+00:00")).astimezone()
        else:
            value = datetime.fromtimestamp(float(code.get("timestamp") or 0)).astimezone()
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return ""


class TeamSelectionDialog(TranslatedDialog):
    def __init__(self, characters, defaults, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(440)
        self.set_dialog_title(self.tr("Create Team"))
        self.viewLayout.addWidget(BodyLabel(self.tr("Select 3 different characters"), self.widget))
        self.combos = []
        for index in range(3):
            combo = ComboBox(self.widget)
            for char_cls in characters:
                combo.addItem(self.tr(get_english_char_name(char_cls)), userData=char_cls.__name__)
            default_name = defaults[index].__name__ if index < len(defaults) else None
            default_index = combo.findData(default_name)
            combo.setCurrentIndex(default_index if default_index >= 0 else index)
            combo.currentIndexChanged.connect(self._update_create_enabled)
            self.combos.append(combo)
            self.viewLayout.addWidget(combo)
        self.yesButton.setText(self.tr("Create Team"))
        self.cancelButton.setText(self.tr("Cancel"))
        self._update_create_enabled()

    def _update_create_enabled(self):
        names = [combo.currentData() for combo in self.combos]
        self.yesButton.setEnabled(len(set(names)) == 3)

    def selected_names(self):
        return [combo.currentData() for combo in self.combos]


class ExportTeamDialog(TranslatedDialog):
    def __init__(self, default_name, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(520)
        self.set_dialog_title(self.tr("Export Team"))
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setText(default_name)
        self.description_edit = TextEdit(self.widget)
        self.description_edit.setFixedHeight(90)
        self.author_edit = LineEdit(self.widget)
        self.version_edit = LineEdit(self.widget)
        self.version_edit.setText("1.0.0")
        for label, field in (
            (self.tr("Name"), self.name_edit), (self.tr("Description"), self.description_edit),
            (self.tr("Author"), self.author_edit), (self.tr("Version"), self.version_edit),
        ):
            self.viewLayout.addWidget(BodyLabel(label, self.widget))
            self.viewLayout.addWidget(field)
        self.yesButton.setText(self.tr("Export"))
        self.cancelButton.setText(self.tr("Cancel"))

    def validate(self):
        values = (self.name_edit.text(), self.description_edit.toPlainText(),
                  self.author_edit.text(), self.version_edit.text())
        if not all(value.strip() for value in values):
            show_info_bar(self.window(), self.tr("All fields are required."),
                          title=self.tr("Missing Information"), error=True)
            return False
        return True

    def values(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "author": self.author_edit.text().strip(),
            "version": self.version_edit.text().strip(),
        }


class ImportTeamDialog(TranslatedDialog):
    def __init__(self, manifest, translated_team, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(560)
        self.set_dialog_title(self.tr("Import Team"))
        self.add_field(self.tr("Name"), manifest["name"])
        self.add_field(self.tr("Description"), manifest["description"])
        self.add_field(self.tr("Team"), translated_team)
        self.add_field(self.tr("Version"), manifest["version"])
        warning = BodyLabel(self.tr("Importing will override the local code for this team."), self.widget)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #d13438;")
        self.viewLayout.addWidget(warning)
        self.yesButton.setText(self.tr("Confirm Import"))
        self.cancelButton.setText(self.tr("Cancel"))


class WorkshopDialog(TranslatedDialog):
    import_requested = Signal(object)

    def __init__(self, codes, team_name, parent=None):
        super().__init__(parent)
        self.widget.setMinimumSize(1040, 500)
        title = self.tr("{team_name} - Team Workshop").format(team_name=team_name)
        self.set_dialog_title(title)
        if not codes:
            empty = BodyLabel(self.tr("No shared code is available for this team."), self.widget)
            empty.setAlignment(Qt.AlignCenter)
            self.viewLayout.addWidget(empty, 1)
        else:
            table = TableWidget(self.widget)
            table.setRowCount(len(codes))
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels([
                self.tr("Name"), self.tr("Description"), self.tr("Author"), self.tr("Version"),
                self.tr("Modified"), self.tr("Size"), "",
            ])
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            for row, code in enumerate(codes):
                values = (
                    code.get("name", ""), code.get("description", ""), code.get("author", ""),
                    code.get("version", ""), format_workshop_local_time(code),
                    code.get("sizeFormatted", str(code.get("size", ""))),
                )
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(str(value)))
                button = PrimaryPushButton(self.tr("Import"), table)
                button.clicked.connect(lambda _checked=False, item=code: self.import_requested.emit(item))
                table.setCellWidget(row, 6, button)
            self.viewLayout.addWidget(table, 1)
        self.yesButton.setText(self.tr("Close"))
        self.hideCancelButton()


class CharacterCodeTab(CustomTab):
    def __init__(self):
        super().__init__()
        self.characters = self._unique_characters()
        self.char_by_name = {char_cls.__name__: char_cls for char_cls in self.characters}
        self.current_team = None
        self.current_char_cls = None
        self.current_team_row = -1
        self.current_member_index = -1
        self.clean_code = ""
        self.loading_editor = False
        self.suppress_selection_guard = False
        self.char_label_by_cls = self._char_labels()
        self.char_feature_index = self._load_char_feature_index()
        self.char_feature_images = {}
        self.char_source_pixmaps = {}
        self.show_char_feature_image = False

        splitter = QSplitter(Qt.Horizontal, self.view)
        splitter.setChildrenCollapsible(False)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.addWidget(BodyLabel(self.tr("Teams")))
        self.team_list = ListWidget(left)
        self.team_list.setMinimumWidth(210)
        self.team_list.setMaximumWidth(300)
        self.team_list.currentRowChanged.connect(self._team_selected)
        left_layout.addWidget(self.team_list, 1)
        team_buttons = QVBoxLayout()
        first_team_button_row = QHBoxLayout()
        self.create_team_button = PrimaryPushButton(FluentIcon.ADD, self.tr("Create Team"))
        self.create_team_button.clicked.connect(self._create_team)
        self.delete_team_button = PushButton(FluentIcon.DELETE, self.tr("Delete Team"))
        self.delete_team_button.clicked.connect(self._delete_team)
        self.workshop_button = PushButton(FluentIcon.LIBRARY, self.tr("Workshop"))
        self.workshop_button.clicked.connect(self._open_workshop)
        first_team_button_row.addWidget(self.create_team_button)
        first_team_button_row.addWidget(self.delete_team_button)
        second_team_button_row = QHBoxLayout()
        self.import_team_button = PushButton(FluentIcon.DOWNLOAD, self.tr("Import Team"))
        self.import_team_button.clicked.connect(self._import_team)
        self.export_team_button = PushButton(FluentIcon.SHARE, self.tr("Export Team"))
        self.export_team_button.clicked.connect(self._export_team)
        second_team_button_row.addWidget(self.workshop_button)
        second_team_button_row.addWidget(self.import_team_button)
        third_team_button_row = QHBoxLayout()
        self.upload_team_button = PushButton(FluentIcon.GITHUB, self.tr("Upload Team"))
        self.upload_team_button.clicked.connect(self._open_upload_team)
        third_team_button_row.addWidget(self.export_team_button)
        third_team_button_row.addWidget(self.upload_team_button)
        team_buttons.addLayout(first_team_button_row)
        team_buttons.addLayout(second_team_button_row)
        team_buttons.addLayout(third_team_button_row)
        left_layout.addLayout(team_buttons)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        top = QHBoxLayout()
        self.char_image_label = QLabel()
        self.char_image_label.setFixedSize(52, 52)
        self.char_image_label.setAlignment(Qt.AlignCenter)
        self.member_combo = ComboBox(right)
        self.member_combo.setMinimumWidth(190)
        self.member_combo.currentIndexChanged.connect(self._member_selected)
        self.ask_ai_button = PushButton(FluentIcon.ROBOT, self.tr("Ask AI"))
        self.ask_ai_button.clicked.connect(self._copy_ask_ai_template)
        top.addWidget(self.char_image_label)
        top.addWidget(BodyLabel(self.tr("Character Code")))
        top.addWidget(self.member_combo)
        top.addStretch(1)
        top.addWidget(self.ask_ai_button)
        right_layout.addLayout(top)

        self.editor = CodeEditor(right)
        self.editor.setMinimumHeight(520)
        self.editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = self.editor.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.editor.setFont(font)
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._editor_text_changed)
        right_layout.addWidget(self.editor, 1)

        bottom = QHBoxLayout()
        self.status_label = BodyLabel("")
        self.reset_button = PushButton(FluentIcon.SYNC, self.tr("Reset to Built In"))
        self.reset_button.clicked.connect(self._reset_current)
        self.save_button = PrimaryPushButton(FluentIcon.SAVE, self.tr("Save"))
        self.save_button.clicked.connect(self._save_current)
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.reset_button)
        bottom.addWidget(self.save_button)
        right_layout.addLayout(bottom)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.add_widget(splitter, stretch=1)
        self._set_editor_enabled(False)
        self._refresh_team_list()

    @property
    def name(self):
        return self.tr("Character Code")

    @property
    def icon(self):
        return FluentIcon.CODE

    def _unique_characters(self):
        return sorted({info["cls"] for info in char_dict.values()},
                      key=lambda cls: get_english_char_name(cls).casefold())

    def _char_labels(self):
        result = {}
        for label, info in char_dict.items():
            result.setdefault(info["cls"], self._label_name(label))
        return result

    def _refresh_team_list(self, selected_team=None):
        selected_team = normalize_team(selected_team) if selected_team else self.current_team
        teams = list_custom_teams()
        self.team_list.blockSignals(True)
        self.team_list.clear()
        selected_row = -1
        for row, team in enumerate(teams):
            display_team = sorted(team, key=lambda name: get_english_char_name(name).casefold())
            label = ", ".join(self.tr(get_english_char_name(name)) for name in display_team)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, list(team))
            self.team_list.addItem(item)
            if team == selected_team:
                selected_row = row
        self.team_list.blockSignals(False)
        if selected_row < 0 and teams:
            selected_row = 0
        if selected_row >= 0:
            self.team_list.setCurrentRow(selected_row)
        else:
            self.current_team = None
            self.current_char_cls = None
            self.member_combo.clear()
            self._set_editor_enabled(False)

    def _team_selected(self, row):
        if self.suppress_selection_guard:
            return
        if self._has_unsaved_changes() and not self._confirm_discard_changes():
            self.suppress_selection_guard = True
            self.team_list.setCurrentRow(self.current_team_row)
            self.suppress_selection_guard = False
            return
        item = self.team_list.item(row)
        if item is None:
            return
        self.current_team = normalize_team(item.data(Qt.UserRole))
        self.current_team_row = row
        self.member_combo.blockSignals(True)
        self.member_combo.clear()
        for class_name in self.current_team:
            self.member_combo.addItem(self.tr(get_english_char_name(class_name)), userData=class_name)
        self.member_combo.blockSignals(False)
        self._set_editor_enabled(True)
        self.member_combo.setCurrentIndex(0)
        self._member_selected(0)

    def _member_selected(self, index):
        if index < 0 or self.current_team is None or self.suppress_selection_guard:
            return
        if self._has_unsaved_changes() and not self._confirm_discard_changes():
            self.suppress_selection_guard = True
            self.member_combo.setCurrentIndex(self.current_member_index)
            self.suppress_selection_guard = False
            return
        self.current_char_cls = self.char_by_name.get(self.member_combo.itemData(index))
        self.current_member_index = index
        self._load_editor_code()
        self._update_char_image()

    def _set_editor_enabled(self, enabled):
        self.editor.setReadOnly(not enabled)
        for widget in (self.member_combo, self.delete_team_button, self.workshop_button,
                       self.export_team_button, self.ask_ai_button, self.reset_button, self.save_button):
            widget.setEnabled(enabled)
        if not enabled:
            self.loading_editor = True
            self.editor.clear()
            self.loading_editor = False
            self.status_label.setText(self.tr("Create or import a team to edit character code."))

    def _load_editor_code(self):
        if self.current_team is None or self.current_char_cls is None:
            return
        code = read_team_char_code(self.current_team, self.current_char_cls)
        self.loading_editor = True
        self.editor.setPlainText(code)
        self.clean_code = code
        self.loading_editor = False
        self.status_label.setText("")
        self._highlight_changed_lines()

    def _editor_text_changed(self):
        if self.loading_editor:
            return
        self._highlight_changed_lines()
        self.status_label.setText(self.tr("Unsaved changes") if self._has_unsaved_changes() else "")

    def _has_unsaved_changes(self):
        return self.current_team is not None and self.editor.toPlainText() != self.clean_code

    def _confirm_discard_changes(self):
        box = MessageBox(self.tr("Unsaved Changes"), self.tr("Discard unsaved character code changes?"), self.window())
        return bool(box.exec())

    def _create_team(self):
        defaults = self._detected_team()
        if len(defaults) != 3:
            defaults = self.characters[:3]
        dialog = TeamSelectionDialog(self.characters, defaults, self.window())
        if not dialog.exec():
            return
        team = normalize_team(dialog.selected_names())
        try:
            create_custom_team(team)
            self._refresh_team_list(team)
            show_info_bar(self.window(), self.tr("Team created."), title=self.tr("Success"))
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _delete_team(self):
        if self.current_team is None:
            return
        team = self.current_team
        display_team = sorted(team, key=lambda name: get_english_char_name(name).casefold())
        team_name = ", ".join(self.tr(get_english_char_name(name)) for name in display_team)
        box = MessageBox(
            self.tr("Delete Team"),
            self.tr("Permanently delete the team {team}?").format(team=team_name),
            self.window(),
        )
        if not box.exec():
            return
        try:
            delete_custom_team(team)
            self._reload_live_team_code(team)
            self.current_team = None
            self.current_char_cls = None
            self._refresh_team_list()
            show_info_bar(self.window(), self.tr("Team deleted."), title=self.tr("Success"))
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _detected_team(self):
        if self.executor is None:
            return []
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(getattr(self.executor, "trigger_tasks", []))
        for task in tasks:
            chars = getattr(task, "chars", None)
            if not chars or len(chars) != 3 or any(char is None for char in chars):
                continue
            classes = []
            for char in chars:
                info = char_dict.get(getattr(char, "char_name", None))
                if info is None:
                    break
                classes.append(info["cls"])
            if len(classes) == 3 and len(set(classes)) == 3:
                return classes
        return []

    def _save_current(self):
        if self.current_team is None or self.current_char_cls is None:
            return
        try:
            code = self.editor.toPlainText()
            path = save_team_char_code(self.current_team, self.current_char_cls, code)
            reloaded = self._reload_live_team_code(self.current_team)
            self.clean_code = code
            self.status_label.setText(self.tr("Saved and reloaded"))
            message = self.tr("Team character code saved.")
            if reloaded:
                message = self.tr("Team character code saved and reloaded for the matching team.")
            show_info_bar(self.window(), message, title=self.tr("Success"))
            self.logger.info(f"saved team char code {self.current_char_cls.__name__}: {path}")
        except Exception as e:
            self.logger.error(f"save team char code failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _reset_current(self):
        if self.current_char_cls is None:
            return
        box = MessageBox(self.tr("Reset Character Code"), self.tr("Reset this character to built in code for this team?"), self.window())
        if not box.exec():
            return
        self.loading_editor = True
        self.editor.setPlainText(read_builtin_char_code(self.current_char_cls))
        self.loading_editor = False
        self._save_current()
        self._highlight_changed_lines()

    def _export_team(self):
        if self.current_team is None:
            return
        if self._has_unsaved_changes():
            show_info_bar(self.window(), self.tr("Save changes before exporting."), title=self.tr("Error"), error=True)
            return
        default_name = "_".join(get_english_char_name(name).replace(" ", "_") for name in self.current_team)
        dialog = ExportTeamDialog(default_name, self.window())
        if not dialog.exec():
            return
        destination = QFileDialog.getExistingDirectory(self.window(), self.tr("Choose Export Folder"))
        if not destination:
            return
        try:
            path = export_custom_team(self.current_team, destination, **dialog.values())
            show_info_bar(self.window(), self.tr("Team exported to {path}").format(path=path), title=self.tr("Success"))
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _import_team(self):
        if self._has_unsaved_changes() and not self._confirm_discard_changes():
            return
        archive_path, _filter = QFileDialog.getOpenFileName(
            self.window(), self.tr("Import Team"), "", self.tr("Zip files (*.zip)"))
        if not archive_path:
            return
        self._preview_and_import_archive(archive_path)

    def _open_workshop(self):
        if self.current_team is None:
            return
        try:
            codes = fetch_workshop_codes(self.current_team)
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Workshop Error"), error=True)
            return
        team_name = ", ".join(sorted(
            (self.tr(get_english_char_name(name)) for name in self.current_team), key=str.casefold
        ))
        dialog = WorkshopDialog(codes, team_name, self.window())
        dialog.import_requested.connect(lambda code: self._import_workshop_code(code, dialog))
        dialog.exec()

    def _import_workshop_code(self, code, parent):
        url = code.get("downloadUrl") or code.get("rawUrl")
        parsed = urlparse(str(url or ""))
        if parsed.scheme != "https" or parsed.hostname not in WORKSHOP_ARCHIVE_HOSTS:
            show_info_bar(parent, self.tr("Workshop download URL is invalid."), title=self.tr("Error"), error=True)
            return
        try:
            with urlopen(url, timeout=30) as response:
                content = response.read(20_000_001)
            if len(content) > 20_000_000:
                raise ValueError(self.tr("Workshop archive is too large."))
            with tempfile.TemporaryDirectory() as temp_dir:
                archive_path = Path(temp_dir) / Path(str(code.get("filename") or "team.zip")).name
                archive_path.write_bytes(content)
                self._preview_and_import_archive(archive_path, expected_team=self.current_team)
        except Exception as e:
            show_info_bar(parent, str(e), title=self.tr("Workshop Error"), error=True)

    def _preview_and_import_archive(self, archive_path, expected_team=None):
        try:
            info = inspect_team_archive(archive_path)
            if expected_team is not None and normalize_team(info["team"]) != normalize_team(expected_team):
                raise ValueError(self.tr("The archive is for a different team."))
        except Exception as e:
            box = MessageBox(self.tr("Invalid Team Archive"), str(e), self.window())
            box.yesButton.setText(self.tr("Close"))
            box.cancelButton.hide()
            box.exec()
            return False
        translated_team = ", ".join(
            self.tr(name.strip()) for name in info["manifest"]["team"].split(",")
        )
        dialog = ImportTeamDialog(info["manifest"], translated_team, self.window())
        if not dialog.exec():
            return False
        try:
            import_custom_team(info)
            self._refresh_team_list(info["team"])
            reloaded = self._reload_live_team_code(info["team"])
            message = self.tr("Team imported.")
            if reloaded:
                message = self.tr("Team imported and reloaded for the matching team.")
            show_info_bar(self.window(), message, title=self.tr("Success"))
            return True
        except Exception as e:
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)
            return False

    def _reload_live_team_code(self, team):
        if self.executor is None:
            return 0
        reloaded = 0
        expected_team = normalize_team(team)
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(getattr(self.executor, "trigger_tasks", []))
        for task in tasks:
            chars = getattr(task, "chars", None)
            if not chars or len(chars) != 3 or any(char is None for char in chars):
                continue
            infos = [char_dict.get(char.char_name) for char in chars]
            if any(info is None for info in infos):
                continue
            if normalize_team(info["cls"] for info in infos) != expected_team:
                continue
            old_types = tuple(type(char) for char in chars)
            apply_team_char_classes(task, chars)
            reloaded += sum(old is not type(char) for old, char in zip(old_types, chars))
        return reloaded

    def _highlight_changed_lines(self):
        if self.current_char_cls is None:
            self.editor.setExtraSelections([])
            return
        builtin_lines = read_builtin_char_code(self.current_char_cls).splitlines()
        current_lines = self.editor.toPlainText().splitlines()
        changed_lines = set()
        for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, builtin_lines, current_lines).get_opcodes():
            if tag != "equal":
                changed_lines.update(range(j1, max(j2, j1 + 1)))
        selections = []
        highlight = QColor(255, 230, 130, 80)
        for line in sorted(changed_lines):
            block = self.editor.document().findBlockByNumber(line)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                selection.format.setBackground(highlight)
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selections.append(selection)
        self.editor.setExtraSelections(selections)

    def _copy_ask_ai_template(self):
        if self.current_char_cls is None:
            return
        class_name = self.current_char_cls.__name__
        template = f'''```python\n{self.editor.toPlainText()}\n```\n\n{self.tr("I want to implement:")}\n\n{self.tr("Please modify the full {class_name} character automation code above.").format(class_name=class_name)}\n\n{self.tr("Return only the complete modified Python code for the whole file, not a patch and not an explanation.")}\n{self.tr("Keep the class name as {class_name}. Preserve imports that are still needed.").format(class_name=class_name)}\n\n{self.tr("Use this BaseChar reference while reasoning about helper methods, task APIs, state, switching, cooldowns, and combat flow:")}\n{BASE_CHAR_URL}\n'''
        QApplication.clipboard().setText(template)
        show_info_bar(self.window(), self.tr("Ask AI template copied. Paste it into an AI chatbot."), title=self.tr("Copied"))

    def _open_upload_team(self):
        QDesktopServices.openUrl(QUrl(UPLOAD_TEAM_URL))

    def _update_char_image(self):
        self.char_image_label.clear()
        if not self.show_char_feature_image:
            return
        pixmap = self._get_char_feature_image(self.char_label_by_cls.get(self.current_char_cls))
        if pixmap is not None and not pixmap.isNull():
            self.char_image_label.setPixmap(pixmap)

    def _load_char_feature_index(self):
        feature_index = {}
        coco_path = Path("assets") / "coco_annotations.json"
        if not coco_path.exists():
            return feature_index
        try:
            data = json.loads(coco_path.read_text(encoding="utf-8"))
            image_by_id = {image["id"]: image["file_name"] for image in data.get("images", [])}
            category_by_id = {category["id"]: category["name"] for category in data.get("categories", [])}
            for annotation in data.get("annotations", []):
                name = category_by_id.get(annotation.get("category_id"))
                image_name = image_by_id.get(annotation.get("image_id"))
                bbox = annotation.get("bbox", [])
                if name and image_name and len(bbox) == 4:
                    feature_index[name] = (coco_path.parent / image_name, tuple(round(value) for value in bbox))
        except Exception as e:
            self.logger.error(f"load char feature image index failed: {e}")
        return feature_index

    def _get_char_feature_image(self, label_name):
        if not label_name:
            return None
        if label_name in self.char_feature_images:
            return self.char_feature_images[label_name]
        image_info = self.char_feature_index.get(label_name)
        if not image_info:
            return None
        image_path, (x, y, width, height) = image_info
        pixmap = self.char_source_pixmaps.get(image_path)
        if pixmap is None:
            pixmap = QPixmap(str(image_path))
            self.char_source_pixmaps[image_path] = pixmap
        if pixmap.isNull():
            return None
        image = pixmap.copy(x, y, width, height).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.char_feature_images[label_name] = image
        return image

    @staticmethod
    def _label_name(label):
        if isinstance(label, tuple):
            label = label[0]
        return getattr(label, "value", label)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.show_char_feature_image:
            self.show_char_feature_image = True
        self._update_char_image()

    def hideEvent(self, event):
        if self._has_unsaved_changes():
            self._confirm_discard_changes()
        super().hideEvent(event)
