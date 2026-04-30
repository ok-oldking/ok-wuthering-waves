from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .geometry import RelBox, pixel_box_to_rel
from .interfaces import Box, OCRText


@dataclass(frozen=True)
class CanvasItem:
    text: str
    box: Box
    confidence: float


class OCRCanvas(QWidget):
    """
    A lightweight, embeddable canvas widget for OCR debugging:
    - show an image
    - overlay OCR boxes
    - allow drag-select region (emits relative coordinates)
    """

    selectionChanged = Signal(object)  # RelBox

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self._pixmap: Optional[QPixmap] = None
        self._image_size: Tuple[int, int] = (0, 0)
        self._items: List[CanvasItem] = []
        self._drag_start: Optional[QPoint] = None
        self._drag_end: Optional[QPoint] = None

    def set_image_from_path(self, path: str) -> None:
        pm = QPixmap(path)
        self._pixmap = pm if not pm.isNull() else None
        if self._pixmap is not None:
            self._image_size = (self._pixmap.width(), self._pixmap.height())
        else:
            self._image_size = (0, 0)
        self._items = []
        self._drag_start = None
        self._drag_end = None
        self.update()

    def set_image_from_bgr(self, frame_bgr) -> None:
        # frame_bgr: numpy array HxWx3 (BGR)
        import numpy as np

        if frame_bgr is None:
            self._pixmap = None
            self._image_size = (0, 0)
            self.update()
            return
        if not isinstance(frame_bgr, np.ndarray) or frame_bgr.ndim != 3:
            raise ValueError("frame_bgr must be a HxWx3 numpy array")
        h, w, _c = frame_bgr.shape
        rgb = frame_bgr[:, :, ::-1].copy()
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._image_size = (w, h)
        self.update()

    def set_ocr_results(self, results: List[OCRText]) -> None:
        self._items = [CanvasItem(r.text, r.box.normalized(), r.confidence) for r in results]
        self.update()

    def clear_overlays(self) -> None:
        self._items = []
        self._drag_start = None
        self._drag_end = None
        self.update()

    def _target_rect(self) -> QRect:
        """Compute the letterboxed rect where pixmap is drawn."""
        if self._pixmap is None:
            return QRect(0, 0, 0, 0)
        iw, ih = self._image_size
        if iw <= 0 or ih <= 0:
            return QRect(0, 0, 0, 0)
        ww, wh = max(1, self.width()), max(1, self.height())
        scale = min(ww / iw, wh / ih)
        dw, dh = int(iw * scale), int(ih * scale)
        ox = (ww - dw) // 2
        oy = (wh - dh) // 2
        return QRect(ox, oy, dw, dh)

    def _to_canvas(self, p: QPoint) -> Optional[Tuple[int, int]]:
        """Map widget coords to image pixel coords."""
        if self._pixmap is None:
            return None
        rect = self._target_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        if not rect.contains(p):
            return None
        iw, ih = self._image_size
        x = p.x() - rect.x()
        y = p.y() - rect.y()
        px = int(round(x * (iw / rect.width())))
        py = int(round(y * (ih / rect.height())))
        px = max(0, min(iw - 1, px))
        py = max(0, min(ih - 1, py))
        return px, py

    def _box_to_widget_rect(self, box: Box) -> Optional[QRect]:
        if self._pixmap is None:
            return None
        rect = self._target_rect()
        iw, ih = self._image_size
        if iw <= 0 or ih <= 0:
            return None
        b = box.normalized()
        sx = rect.width() / iw
        sy = rect.height() / ih
        x1 = int(rect.x() + b.x1 * sx)
        y1 = int(rect.y() + b.y1 * sy)
        x2 = int(rect.x() + b.x2 * sx)
        y2 = int(rect.y() + b.y2 * sy)
        return QRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(20, 20, 20))

        if self._pixmap is None:
            p.end()
            return

        target = self._target_rect()
        p.drawPixmap(target, self._pixmap)

        # OCR overlays
        pen = QPen(QColor(255, 77, 79, 220))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(255, 77, 79, 50)))
        for item in self._items:
            r = self._box_to_widget_rect(item.box)
            if r is None:
                continue
            p.drawRect(r)
            label = f"{item.text}  ({item.confidence:.2f})"
            p.setPen(QPen(QColor(255, 224, 138, 230)))
            p.drawText(r.x() + 2, max(12, r.y() - 4), label)
            p.setPen(pen)

        # Selection overlay
        if self._drag_start is not None and self._drag_end is not None:
            p.setPen(QPen(QColor(0, 255, 136, 230), 2, Qt.DashLine))
            p.setBrush(QBrush(QColor(0, 255, 136, 40)))
            sel = QRect(self._drag_start, self._drag_end).normalized()
            p.drawRect(sel)

        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._drag_start = event.position().toPoint()
        self._drag_end = self._drag_start
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        self._drag_end = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        if self._drag_start is None:
            return
        self._drag_end = event.position().toPoint()

        p1 = self._to_canvas(self._drag_start)
        p2 = self._to_canvas(self._drag_end)
        self._drag_start = None
        self._drag_end = None
        self.update()
        if p1 is None or p2 is None:
            return
        (x1, y1), (x2, y2) = p1, p2
        box = Box(x1, y1, x2, y2).normalized()
        iw, ih = self._image_size
        rel = pixel_box_to_rel(box, iw, ih).normalized()
        self.selectionChanged.emit(rel)

