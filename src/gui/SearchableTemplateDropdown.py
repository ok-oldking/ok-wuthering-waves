"""Searchable character-template selector for the Echo Score config tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter
from qfluentwidgets import EditableComboBox

from src.echo_score import matching_template_names, resolve_template_name


class TemplateSearchComboBox(EditableComboBox):
    """Prevent arbitrary typed text from becoming a persisted template."""

    def _onReturnPressed(self):
        exact_index = self.findText(self.text())
        if exact_index >= 0:
            self.setCurrentIndex(exact_index)
            return
        matches = matching_template_names(self.text())
        if len(matches) == 1:
            self.setCurrentIndex(self.findText(matches[0]))


def install_searchable_template_dropdown(main_window):
    tabs = getattr(main_window, "global_config_tabs", ())
    tab = next((item for item in tabs if item.option.name == "声骸评分"), None)
    if tab is None:
        return None
    widget = tab.config_widget_by_key.get("角色评分模板")
    if widget is None or isinstance(widget.combo_box, TemplateSearchComboBox):
        return getattr(widget, "combo_box", None)

    old_combo = widget.combo_box
    combo = TemplateSearchComboBox(widget)
    combo.addItems(widget.tr_options)
    combo.setFixedWidth(330)
    combo.setPlaceholderText("输入角色名搜索")

    selected = resolve_template_name(widget.config.get(widget.key))
    if selected != widget.config.get(widget.key):
        widget.update_config(selected)
    translated = next(
        (text for text, value in widget.tr_dict.items() if value == selected),
        selected,
    )
    combo.setCurrentIndex(combo.findText(translated))

    completer = QCompleter(widget.tr_options, combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)

    def persist_exact_match(text):
        option = widget.tr_dict.get(text)
        if option is not None:
            widget.update_config(option)

    combo.currentTextChanged.connect(persist_exact_match)
    widget.layout.replaceWidget(old_combo, combo)
    old_combo.deleteLater()
    widget.combo_box = combo
    widget._template_completer = completer
    return combo
