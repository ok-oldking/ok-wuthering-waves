"""地图资源下载/解压的进度弹窗与跨线程 GUI 助手。

框架自带的加载弹窗（``ok.gui.widget.StartLoadingDialog``）只有不确定进度的转圈，没有
百分比进度条，因此这里基于 ``qfluentwidgets.MessageBoxBase`` + ``ProgressBar`` 自建一个
Fluent 风格的进度弹窗：

- :class:`AssetsProgressDialog`：标题 + 进度条 + 状态文本，下载/解压期间禁用关闭按钮，
  结束（成功或失败）后启用；非模态，用户仍可继续操作主界面。
- :class:`AssetsGuiHelper`：归属 GUI 线程的信号中转对象。下载跑在后台线程，只能通过
  ``emit`` 触达 GUI；助手的槽在 GUI 线程执行，负责创建/更新/结束弹窗，以及下载失败时
  弹出“手动下载”提示框。

本模块只在有 GUI 的运行环境中被惰性导入（任务侧 ``_ensure_assets_gui``），因此可以在
模块顶层导入 Qt / qfluentwidgets。
"""

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, MessageBoxBase, ProgressBar, SubtitleLabel

from ok import Logger, og

logger = Logger.get_logger(__name__)


def _tr(text):
    """经 ``og.app.tr`` 走 gettext 翻译，GUI 不可用时原样返回。"""
    try:
        return og.app.tr(text)
    except Exception:  # pragma: no cover - og.app 未初始化时
        return text


class AssetsProgressDialog(MessageBoxBase):
    """带百分比进度条的资源下载/解压弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.title_label = SubtitleLabel(_tr('Downloading map assets'))
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.status_label = BodyLabel('')
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignLeft)

        self.viewLayout.setSpacing(12)
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.progress_bar)
        self.viewLayout.addWidget(self.status_label)
        self.widget.setMinimumWidth(460)

        self.yesButton.setText(_tr('Close'))
        self.cancelButton.hide()
        self.reset()

    def reset(self):
        """回到“进行中”初始态，供重复下载复用同一弹窗。"""
        self.title_label.setText(_tr('Downloading map assets'))
        self.progress_bar.setValue(0)
        self.status_label.setText('')
        self.yesButton.setEnabled(False)

    def set_progress(self, message, percent):
        """更新状态文本与进度条；``percent`` 为负数时保持进度条原值。"""
        self.status_label.setText(message)
        if percent is not None and percent >= 0:
            self.progress_bar.setValue(int(min(percent, 100)))

    def set_finished(self, message, success):
        """结束（成功/失败）：写入结果文案并允许关闭。"""
        self.status_label.setText(message)
        if success:
            self.progress_bar.setValue(100)
        self.title_label.setText(
            _tr('Map assets updated') if success
            else _tr('Map assets download failed')
        )
        self.yesButton.setEnabled(True)


class AssetsGuiHelper(QObject):
    """把后台下载线程的进度/结果搬到 GUI 线程展示的信号中转对象。

    四个信号都可以从任意线程 ``emit``：对象归属 GUI 线程，跨线程连接自动走队列投递，
    槽函数始终在 GUI 线程执行（``started`` 负责建/重置弹窗，``progress`` 刷新进度，
    ``finished`` 收尾，``alert`` 弹“手动下载”提示）。
    """

    started = Signal()
    progress = Signal(str, float)
    finished = Signal(str, bool)
    alert = Signal(str, str)

    def __init__(self):
        super().__init__()
        self._dialog = None
        self.started.connect(self._on_started)
        self.progress.connect(self._on_progress)
        self.finished.connect(self._on_finished)
        self.alert.connect(self._on_alert)

    # -- 槽（GUI 线程） ------------------------------------------------
    @Slot()
    def _on_started(self):
        dialog = self._ensure_dialog()
        if dialog is None:
            return
        dialog.reset()
        dialog.show()

    @Slot(str, float)
    def _on_progress(self, message, percent):
        dialog = self._dialog
        if dialog is None:
            return
        dialog.set_progress(message, percent)

    @Slot(str, bool)
    def _on_finished(self, message, success):
        dialog = self._dialog
        if dialog is None:
            return
        dialog.set_finished(message, success)

    @Slot(str, str)
    def _on_alert(self, title, message):
        from ok.gui.util.Alert import show_alert
        show_alert(title, message)

    # -- 弹窗生命周期 --------------------------------------------------
    def _ensure_dialog(self):
        """创建（或复用）进度弹窗；创建失败时返回 ``None``，只走面板状态展示。"""
        dialog = self._dialog
        if dialog is not None:
            try:
                dialog.isVisible()
                return dialog
            except RuntimeError:  # pragma: no cover - 弹窗已被销毁
                self._dialog = None
        # MessageBoxBase 依赖 parent 的几何来铺遮罩，没有主窗口时无法创建弹窗，
        # 此时只保留面板状态展示（info_set），不影响下载本身。
        parent = getattr(og, 'main_window', None)
        if parent is None:
            logger.warning('[MapAssets] no main window, skip progress dialog')
            return None
        try:
            dialog = AssetsProgressDialog(parent)
            dialog.destroyed.connect(lambda *_: self._clear_dialog())
        except Exception as e:  # pragma: no cover - Qt 运行时相关
            logger.warning(f'[MapAssets] create progress dialog failed: {e}')
            return None
        self._dialog = dialog
        return dialog

    def _clear_dialog(self):
        self._dialog = None

    def close_dialog(self):
        """关闭并释放弹窗（任务销毁时调用）。"""
        dialog = self._dialog
        self._dialog = None
        if dialog is None:
            return
        try:
            dialog.close()
            dialog.deleteLater()
        except Exception:  # pragma: no cover - Qt 运行时相关
            pass


def create_gui_helper():
    """在 GUI 线程创建 :class:`AssetsGuiHelper`，无 QApplication 时返回 ``None``。"""
    app = QApplication.instance()
    if app is None:
        return None
    helper = AssetsGuiHelper()
    helper.moveToThread(app.thread())
    return helper
