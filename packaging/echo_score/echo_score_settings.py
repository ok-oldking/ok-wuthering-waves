"""Visible settings card for the portable Echo Score package."""

from ok import BaseTask
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter
from qfluentwidgets import EditableComboBox, SwitchButton

from echo_score import (
    DEFAULT_TEMPLATE, matching_template_names, resolve_template_name, template_names,
)


class _TemplateSearchComboBox(EditableComboBox):
    def _onReturnPressed(self):
        exact_index = self.findText(self.text())
        if exact_index >= 0:
            self.setCurrentIndex(exact_index)
            return
        matches = matching_template_names(self.text())
        if len(matches) == 1:
            self.setCurrentIndex(self.findText(matches[0]))


class EchoScoreSettingsTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "声骸评分设置"
        self.description = "配置评分模板；修改后立即生效"
        self.default_config.update({
            "启用声骸评分": True,
            "自动匹配评分模板": False,
            "角色评分模板": DEFAULT_TEMPLATE,
            "Show Debug Boxes": False,
        })
        self.config_type.update({
            "启用声骸评分": {"hidden": True},
            "角色评分模板": {"type": "drop_down", "options": template_names()},
            # Imported packages are a user-facing distribution. OCR boxes are
            # a development diagnostic and must not appear in this UI.
            "Show Debug Boxes": {"hidden": True},
        })
        self.config_description.update({
            "启用声骸评分": "启用后台识别、词条框体和实时评分",
            "自动匹配评分模板": "根据声骸查看界面的“装配中”角色自动选择模板",
            "角色评分模板": "选择 XW-UID 角色/流派评分模板",
            "Show Debug Boxes": "显示 OK Script 的 OCR 调试框",
        })

    def _install_total_switch(self, card):
        if getattr(card, "_echo_total_switch", None) is not None:
            return
        for button in (card.start_button, card.pause_button, card.stop_button):
            if button is not None:
                button.hide()
        switch = SwitchButton(parent=card)
        switch.setOnText("已启用")
        switch.setOffText("已停用")
        switch.setChecked(bool(self.config.get("启用声骸评分", True)))
        switch.checkedChanged.connect(
            lambda checked: self.config.__setitem__("启用声骸评分", bool(checked))
        )
        # Stop TaskCard from restoring its one-shot Start button whenever any
        # other task changes state, and let its normal layout rebuild retain
        # our persistent switch.
        card.onetime = False
        card.all_buttons.append(switch)
        card._rebuild_button_layout()
        card._echo_total_switch = switch

    def _install_search_combo(self, card):
        widget = card.config_widget_by_key.get("角色评分模板")
        if widget is None or isinstance(widget.combo_box, _TemplateSearchComboBox):
            return
        old_combo = widget.combo_box
        combo = _TemplateSearchComboBox(widget)
        combo.addItems(widget.tr_options)
        combo.setFixedWidth(330)
        combo.setPlaceholderText("输入角色名搜索")
        selected = resolve_template_name(widget.config.get(widget.key))
        translated = next((text for text, value in widget.tr_dict.items()
                           if value == selected), selected)
        combo.setCurrentIndex(combo.findText(translated))
        completer = QCompleter(widget.tr_options, combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(completer)
        combo.currentTextChanged.connect(
            lambda text: widget.update_config(widget.tr_dict[text])
            if text in widget.tr_dict else None
        )
        widget.layout.replaceWidget(old_combo, combo)
        old_combo.deleteLater()
        widget.combo_box = combo
        widget._template_completer = completer

    def validate_config(self, key, value):
        if key == "角色评分模板" and resolve_template_name(value) != value:
            return "请选择列表中的评分模板"
        return None

    def run(self):
        # Kept for compatibility with the host's imported-task registry. The
        # card exposes a persistent switch, so users never need to run it.
        return


def _patch_imported_task_card():
    """Customize the card synchronously, before the host can display it.

    ``post_init`` runs before ``MainWindow`` creates imported tabs in official
    OKWW, so a timer started there is not a reliable UI hook. Wrapping the
    existing card constructor makes the customization deterministic while
    leaving every non-Echo task untouched.
    """
    from ok.ui.qt.tasks.TaskCard import TaskCard

    if getattr(TaskCard, "_echo_score_card_patch", False):
        return
    original_init = TaskCard.__init__

    def patched_init(card, task, onetime):
        original_init(card, task, onetime)
        if task.__class__.__name__ != "EchoScoreSettingsTask":
            return
        task._install_total_switch(card)
        task._install_search_combo(card)
        card.setExpand(True)

    TaskCard.__init__ = patched_init
    TaskCard._echo_score_card_patch = True


_patch_imported_task_card()
