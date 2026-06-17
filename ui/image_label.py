import os
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QPainter, QPalette, QPen
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPoint, QRect


class InteractiveImageLabel(QLabel):
    crop_saved = pyqtSignal(str, str, QPixmap, tuple)
    point_updated = pyqtSignal(int, int, str)
    bbox_changed = pyqtSignal(tuple)  # (xmin, ymin, xmax, ymax)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setBackgroundRole(QPalette.Base)
        self.setScaledContents(False)

        self._pixmap = None
        self._zoom = 1.0
        self._offset = QPoint(0, 0)
        self._dragging = False
        self._last_mouse_pos = QPoint()

        self._crop_mode = False
        self._crop_start = None
        self._crop_rect = None

        self._point_mode = False
        self._points = {}
        self._current_category = None
        self._color_map = {}

        self._bbox_mode = False
        self._bbox_start = None
        self._bbox_rect = QRect()
        self._bboxes = []
        self._current_bbox = None

    def set_bbox_mode(self, enabled: bool):
        self._bbox_mode = enabled
        self.setMouseTracking(enabled)

    def set_color_map(self, color_map: dict):
        self._color_map = color_map

    def set_point_mode(self, enabled: bool, category: str = None):
        self._point_mode = enabled
        self._current_category = category
        self.setMouseTracking(enabled)

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap

        if not self._pixmap or self._pixmap.isNull():
            self._zoom = 1.0
            self._offset = QPoint(0, 0)
            self.update()
            return

        label_width = self.width()
        label_height = self.height()
        pixmap_width = self._pixmap.width()
        pixmap_height = self._pixmap.height()

        scale_x = label_width / pixmap_width
        scale_y = label_height / pixmap_height
        self._zoom = min(scale_x, scale_y)

        scaled_width = pixmap_width * self._zoom
        scaled_height = pixmap_height * self._zoom
        x_offset = (label_width - scaled_width) / 2
        y_offset = (label_height - scaled_height) / 2
        self._offset = QPoint(int(x_offset), int(y_offset))
        self.update()

    def get_current_bbox(self):
        """Restituisce l'ultimo bbox disegnato come tuple (xmin, ymin, xmax, ymax)."""
        if self._bboxes:
            return self._bboxes[-1]
        return None

    def set_image_path(self, path: str):
        self._image_path = path

    def set_crop_mode(self, enabled: bool):
        self._crop_mode = enabled
        self._crop_start = None
        self._crop_rect = None
        self.update()

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        zoom_factor = 1.25 if delta > 0 else 0.8
        old_pos = event.pos()

        old_x = (old_pos.x() - self._offset.x()) / self._zoom
        old_y = (old_pos.y() - self._offset.y()) / self._zoom

        self._zoom *= zoom_factor

        new_x = old_x * self._zoom + self._offset.x()
        new_y = old_y * self._zoom + self._offset.y()
        self._offset += old_pos - QPoint(int(new_x), int(new_y))
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            self._zoom = min(
                self.width() / self._pixmap.width(),
                self.height() / self._pixmap.height()
            )
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.Base))

        if self._pixmap and not self._pixmap.isNull():
            scaled_pixmap = self._pixmap.scaled(
                self._pixmap.size() * self._zoom,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(self._offset, scaled_pixmap)

        # Rettangolo crop temporaneo
        if self._crop_mode and self._crop_rect:
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            painter.drawRect(self._crop_rect)

        # Punti salvati
        if self._points:
            for category, point in self._points.items():
                px = int(point['x'] * self._zoom + self._offset.x())
                py = int(point['y'] * self._zoom + self._offset.y())
                color = self._color_map.get(category, Qt.magenta)
                painter.setPen(QPen(color, 5, Qt.SolidLine))
                size = 10
                painter.drawLine(px - size, py - size, px + size, py + size)
                painter.drawLine(px + size, py - size, px - size, py + size)

        # Rettangolo bbox temporaneo (mentre si disegna)
        if self._bbox_mode and not self._bbox_rect.isNull():
            painter.setPen(QPen(Qt.yellow, 2, Qt.SolidLine))
            painter.drawRect(self._bbox_rect)

        # Bounding box salvati
        if self._bboxes:
            for item in self._bboxes:
                bbox = item['bbox'] if isinstance(item, dict) else item
                x1 = int(bbox[0] * self._zoom + self._offset.x())
                y1 = int(bbox[1] * self._zoom + self._offset.y())
                x2 = int(bbox[2] * self._zoom + self._offset.x())
                y2 = int(bbox[3] * self._zoom + self._offset.y())
                painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
                painter.drawRect(QRect(QPoint(x1, y1), QPoint(x2, y2)))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._crop_mode:
                self._crop_start = event.pos()
                self._crop_rect = QRect(self._crop_start, QSize())
                self.update()
            elif self._bbox_mode:
                self._bbox_start = event.pos()
                self._bbox_rect = QRect(self._bbox_start, QSize())
                self._bboxes = []
                self._current_bbox = None
                self.update()
            elif self._point_mode:
                if self._current_category:
                    x = (event.pos().x() - self._offset.x()) / self._zoom
                    y = (event.pos().y() - self._offset.y()) / self._zoom
                    self._points[self._current_category] = {'x': x, 'y': y}
                    self.point_updated.emit(int(x), int(y), self._current_category)
                    self.update()
            else:
                self._dragging = True
                self._last_mouse_pos = event.pos()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Non resettare se si è in point mode
            if self._point_mode:
                super().mouseDoubleClickEvent(event)
                return

            # Reset zoom e offset per adattare l'immagine al widget
            if self._pixmap and not self._pixmap.isNull():
                scale_x = self.width() / self._pixmap.width()
                scale_y = self.height() / self._pixmap.height()
                self._zoom = min(scale_x, scale_y)

                scaled_width = self._pixmap.width() * self._zoom
                scaled_height = self._pixmap.height() * self._zoom
                x_offset = (self.width() - scaled_width) / 2
                y_offset = (self.height() - scaled_height) / 2
                self._offset = QPoint(int(x_offset), int(y_offset))

                self.update()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._crop_mode and self._crop_start:
            self._crop_rect = QRect(self._crop_start, event.pos()).normalized()
            self.update()
        elif self._bbox_mode and self._bbox_start:
            self._bbox_rect = QRect(self._bbox_start, event.pos()).normalized()
            self.update()
        elif self._dragging and self._pixmap:
            delta = event.pos() - self._last_mouse_pos
            self._offset += delta
            self._last_mouse_pos = event.pos()
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._bbox_mode and self._bbox_start:
            x1 = int((self._bbox_rect.left() - self._offset.x()) / self._zoom)
            y1 = int((self._bbox_rect.top() - self._offset.y()) / self._zoom)
            x2 = int((self._bbox_rect.right() - self._offset.x()) / self._zoom)
            y2 = int((self._bbox_rect.bottom() - self._offset.y()) / self._zoom)

            bbox = (x1, y1, x2, y2)
            self._current_bbox = bbox
            self._bboxes = [bbox]

            self._bbox_rect = QRect()
            self._bbox_start = None
            self.bbox_changed.emit(self._current_bbox)
            self.update()

        elif self._crop_mode and event.button() == Qt.LeftButton:
            self._crop_start = None
            self.update()
        elif event.button() == Qt.LeftButton:
            self._dragging = False
        else:
            super().mouseReleaseEvent(event)

    def perform_crop(self):
        if not self._pixmap or not self._crop_rect or self._crop_rect.isNull():
            return

        x = max(0, int((self._crop_rect.left() - self._offset.x()) / self._zoom))
        y = max(0, int((self._crop_rect.top() - self._offset.y()) / self._zoom))
        w = max(1, int(self._crop_rect.width() / self._zoom))
        h = max(1, int(self._crop_rect.height() / self._zoom))

        cropped = self._pixmap.copy(x, y, w, h)
        if cropped.isNull():
            return

        bbox = (x, y, x + w, y + h)
        self.crop_saved.emit(self._image_path, None, cropped, bbox)

        self._crop_start = None
        self._crop_rect = None
        self.update()