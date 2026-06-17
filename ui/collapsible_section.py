from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve


class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self._is_collapsed = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Pulsante titolo
        self.toggle_button = QPushButton(f"▼  {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle_button.setFixedHeight(30)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 8px;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 4px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle)
        self.main_layout.addWidget(self.toggle_button)

        # Contenitore del contenuto
        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(4)
        self.main_layout.addWidget(self.content_widget)

    def toggle(self):
        self._is_collapsed = not self._is_collapsed
        self.content_widget.setVisible(not self._is_collapsed)
        title = self.toggle_button.text()[3:]  # rimuove "▼  " o "▶  "
        if self._is_collapsed:
            self.toggle_button.setText(f"▶  {title}")
        else:
            self.toggle_button.setText(f"▼  {title}")

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)