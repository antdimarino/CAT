import os
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout,
    QPushButton, QFileDialog, QGroupBox, QButtonGroup, QScrollArea,
    QToolBox, QSplitter, QGridLayout, QGraphicsDropShadowEffect,
    QTableWidget, QTableWidgetItem, QAction, QStackedLayout, QSizePolicy,
    QGraphicsOpacityEffect, QProgressBar, QMenu, QMessageBox, QLineEdit, QApplication
)
from PyQt5.QtGui import QPixmap, QIcon, QColor, QPalette
from PyQt5.QtCore import Qt, QSize, QTimer, QPropertyAnimation

from ui.image_label import InteractiveImageLabel
from core.csv_manager import (
    load_config, save_config, load_csv,
    save_annotations, load_cropped_csv, get_species_name,
    sync_csv_with_folder
)
from core.export_manager import export_to_json
from utils.helpers import get_next_crop_index, resource_path
from ui.statistics_window import StatisticsWindow
from ui.collapsible_section import CollapsibleSection


class ImageBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Concept Annotation Tool")
        self.setGeometry(100, 100, 1200, 600)

        self.folder_path = ""
        self.image_list = []
        self.current_index = -1
        self.questions = []
        self.loaded_bboxes = {}
        self.csv_data = None
        self.csv_table = None
        self.csv_path = None
        self.veil_buttons = []
        self.ring_volva_buttons = []
        self._points = {}

        self.category_colors = [
            Qt.red, Qt.blue, Qt.green, Qt.yellow, Qt.cyan, Qt.magenta,
            Qt.darkRed, Qt.darkBlue, Qt.darkGreen, Qt.darkYellow,
            Qt.darkCyan, Qt.darkMagenta
        ]

        self.crop_mode = False
        self.crop_counter = 0
        self.cropped_csv_data = None
        self.session_count = 0

        self.questions_for_category = {}
        self.answer_widgets = {}
        self.category_visibility_buttons = {}
        self.category_point_widgets = {}

        self.init_ui()

    def init_ui(self):
        self.setFocusPolicy(Qt.StrongFocus)

        # Central widget obbligatorio per QMainWindow
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Inizializza csv_table prima di usarlo nello splitter
        self.csv_table = QTableWidget()
        self.csv_table.setColumnCount(2)
        self.csv_table.setHorizontalHeaderLabels(["Attribute", "Value"])
        self.csv_table.horizontalHeader().setStretchLastSection(True)

        # --- Menu bar nativa ---
        tools_menu = self.menuBar().addMenu("Tools")

        self.crop_action = QAction("Enable Crop Mode", self)
        self.crop_action.triggered.connect(self.toggle_crop_mode_action)
        tools_menu.addAction(self.crop_action)

        self.bbox_action = QAction("Enable Bbox Mode", self)
        self.bbox_action.triggered.connect(self.toggle_bbox_mode_action)
        tools_menu.addAction(self.bbox_action)

        tools_menu.addSeparator()
        load_questions_action = QAction("Load questions file...", self)
        load_questions_action.triggered.connect(self.handle_load_questions)
        tools_menu.addAction(load_questions_action)

        tools_menu.addSeparator()

        export_action = QAction("Export JSON", self)
        export_action.triggered.connect(self.handle_export_json)
        tools_menu.addAction(export_action)

        # Menu statistiche
        stats_menu = self.menuBar().addMenu("Statistics")
        stats_action = QAction("View Attribute Distribution", self)
        stats_action.triggered.connect(self.show_statistics_window)
        stats_menu.addAction(stats_action)

        # Menu View per il tema
        view_menu = self.menuBar().addMenu("View")
        self.theme_action = QAction("Switch to Dark Theme", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_action)

        # --- Pannello sinistro ---
        sidebar_top = QVBoxLayout()
        sidebar_top.setSpacing(4)
        sidebar_top.setContentsMargins(4, 4, 4, 4)

        self.load_button = QPushButton("Load Directory")
        self.load_button.clicked.connect(self.load_folder)
        sidebar_top.addWidget(self.load_button)

        self.csv_info_label = QLabel("⚠ No CSV loaded")
        self.csv_info_label.setAlignment(Qt.AlignCenter)
        self.csv_info_label.setStyleSheet("font-weight: bold;")
        sidebar_top.addWidget(self.csv_info_label)

        # --- Sezione Navigazione ---
        nav_section = CollapsibleSection("Navigation")

        # Filtri
        filter_layout = QHBoxLayout()
        self.filter_all_btn = QPushButton("All")
        self.filter_unanswered_btn = QPushButton("Todo")
        self.filter_answered_btn = QPushButton("Done")
        for btn in [self.filter_all_btn, self.filter_unanswered_btn, self.filter_answered_btn]:
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            filter_layout.addWidget(btn)
        self.filter_all_btn.setChecked(True)
        self.filter_all_btn.clicked.connect(lambda: self.apply_filter("all"))
        self.filter_unanswered_btn.clicked.connect(lambda: self.apply_filter("unanswered"))
        self.filter_answered_btn.clicked.connect(lambda: self.apply_filter("answered"))
        nav_section.add_layout(filter_layout)

        # Barra ricerca
        self.search_bar = QLineEdit()
        self.search_bar.addAction(
            QIcon(resource_path('ui_icons/search.png')),
            QLineEdit.LeadingPosition
        )
        self.search_bar.setPlaceholderText("Search image...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self.apply_search)
        nav_section.add_widget(self.search_bar)

        # Lista immagini
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(48, 48))
        self.list_widget.setSpacing(2)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        nav_section.add_widget(self.list_widget)

        # Navigazione
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self.prev_image)
        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.next_image)
        self.jump_button = QPushButton("")
        self.jump_button.setIcon(QIcon(resource_path('ui_icons/right-arrow.png')))
        self.jump_button.setIconSize(QSize(24, 24))
        self.jump_button.setFixedSize(36, 36)
        self.jump_button.setToolTip("Jump to first unanswered image")
        self.jump_button.clicked.connect(self.jump_to_first_unanswered)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.jump_button)
        nav_section.add_layout(nav_layout)

        sidebar_top.addWidget(nav_section)

        # --- Sezione Statistiche ---
        stats_section = CollapsibleSection("Statistics")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFormat("%p%")
        stats_section.add_widget(self.progress_bar)

        self.stat_total_label    = QLabel("Total images: 0")
        self.stat_answered_label = QLabel("Annotated: 0")
        self.stat_missing_label  = QLabel("Not annotated: 0")
        self.stat_session_label  = QLabel("Annotated this session: 0")

        for lbl in [
            self.stat_total_label,
            self.stat_answered_label,
            self.stat_missing_label,
        ]:
            lbl.setAlignment(Qt.AlignLeft)
            lbl.setStyleSheet("font-size: 12px;")
            stats_section.add_widget(lbl)

        separator = QLabel("─────────────────")
        separator.setAlignment(Qt.AlignCenter)
        separator.setStyleSheet("font-size: 10px;")
        stats_section.add_widget(separator)

        self.stat_session_label.setAlignment(Qt.AlignLeft)
        self.stat_session_label.setStyleSheet("font-size: 12px;")
        stats_section.add_widget(self.stat_session_label)

        sidebar_top.addWidget(stats_section)
        sidebar_top.addStretch()

        sidebar_top_widget = QWidget()
        sidebar_top_widget.setLayout(sidebar_top)
        
        sidebar_splitter = QSplitter(Qt.Vertical)
        sidebar_splitter.addWidget(sidebar_top_widget)
        sidebar_splitter.addWidget(self.csv_table)
        sidebar_splitter.setSizes([400, 200])

        # --- Pannello centrale: immagine ---
        self.image_label = InteractiveImageLabel()
        self.image_label.crop_saved.connect(self.add_crop_to_csv)
        self.image_label.point_updated.connect(self.update_coordinates_label)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid black; background-color: #eee;")
        self.image_label.setMinimumSize(400, 400)
        self.image_label.bbox_changed.connect(self.update_bbox_coordinates_label)

        self.image_counter_label = QLabel("No image loaded")
        self.image_counter_label.setAlignment(Qt.AlignCenter)
        self.image_counter_label.setStyleSheet("font-size: 12px;")

        # --- Pannello crop ---
        self.crop_panel = QWidget()
        crop_layout = QVBoxLayout()
        self.crop_button_confirm = QPushButton("Crop")
        self.crop_button_confirm.clicked.connect(self.image_label.perform_crop)
        self.crop_button_copy = QPushButton("Copy Whole Image")
        copy_action = QAction(self)
        copy_action.triggered.connect(self.move_image_to_cropped)
        self.addAction(copy_action)
        self.crop_button_copy.clicked.connect(self.move_image_to_cropped)
        self.crop_button_cancel = QPushButton("Cancel")
        self.crop_button_cancel.clicked.connect(lambda: self.toggle_crop_mode(False))
        self.crop_button_confirm.setFocusPolicy(Qt.NoFocus)
        self.crop_button_copy.setFocusPolicy(Qt.NoFocus)
        self.crop_button_cancel.setFocusPolicy(Qt.NoFocus)
        crop_layout.addWidget(self.crop_button_confirm)
        crop_layout.addWidget(self.crop_button_copy)
        crop_layout.addStretch(1)
        crop_layout.addWidget(self.crop_button_cancel)
        crop_layout.addStretch()
        self.crop_panel.setLayout(crop_layout)

        # --- Pannello bbox ---
        self.bbox_mode_widget = QWidget()
        bbox_mode_layout = QVBoxLayout()
        self.bbox_mode_label = QLabel("<b>Bounding Box Mode</b>: Inactive")
        self.bbox_mode_label.setAlignment(Qt.AlignCenter)
        self.bbox_coordinates_label = QLabel("Coordinates: (n/a, n/a)")
        self.bbox_coordinates_label.setAlignment(Qt.AlignCenter)
        bbox_mode_layout.addWidget(self.bbox_mode_label)
        bbox_mode_layout.addWidget(self.bbox_coordinates_label)
        bbox_mode_layout.addStretch(1)
        self.bbox_submit_button = QPushButton("Submit Bbox")
        self.bbox_submit_button.setFocusPolicy(Qt.NoFocus)
        self.bbox_submit_button.clicked.connect(self.submit_current_bbox)
        bbox_mode_layout.addWidget(self.bbox_submit_button)
        self.bbox_mode_widget.setLayout(bbox_mode_layout)

        # --- Pannello destro: domande ---
        self.question_box = QVBoxLayout()
        self.toolbox = QToolBox()
        self.toolbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.question_box.addWidget(self.toolbox)

        self.question_widget = QWidget()
        self.question_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.question_widget.setLayout(self.question_box)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.save_answers)
        self.question_box.addWidget(self.submit_button)

        self.question_area = QScrollArea()
        self.question_area.setWidgetResizable(True)
        self.question_area.setWidget(self.question_widget)

        self.right_panel_stack = QStackedLayout()
        self.right_panel_stack.addWidget(self.question_area)   # index 0
        self.right_panel_stack.addWidget(self.crop_panel)      # index 1
        self.right_panel_stack.addWidget(self.bbox_mode_widget) # index 2

        self.right_panel_container = QWidget()
        self.right_panel_container.setLayout(self.right_panel_stack)

        # Pannello centrale con immagine e contatore
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)
        center_layout.addWidget(self.image_label, stretch=1)
        center_layout.addWidget(self.image_counter_label, stretch=0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(sidebar_splitter)
        self.splitter.addWidget(center_widget)
        self.splitter.addWidget(self.right_panel_container)
        self.splitter.setSizes([200, 730, 300])

        main_layout.addWidget(self.splitter)
        self.load_questions(resource_path("questions.txt"))
        self.set_ui_mode("none")

    # ------------------------------------------------------------------ #
    #  UI Modes                                                            #
    # ------------------------------------------------------------------ #

    def set_ui_mode(self, mode: str, category: str = None):
        for widgets in self.category_point_widgets.values():
            widgets["widget"].hide()

        self.image_label.set_point_mode(False, None)
        self.image_label.set_crop_mode(False)
        self.image_label.set_bbox_mode(False)

        if mode not in ["crop", "bbox"]:
            self.right_panel_stack.setCurrentIndex(0)

        if mode == "point":
            self.image_label.set_point_mode(True, category)
            self.category_point_widgets[category]["widget"].show()
            self.category_point_widgets[category]["mode_label"].setText(
                f"<b>Point Mode</b>: Active - {category}"
            )
        elif mode == "crop":
            self.image_label.set_crop_mode(True)
            self.right_panel_stack.setCurrentIndex(1)
        elif mode == "bbox":
            self.image_label.set_bbox_mode(True)
            self.right_panel_stack.setCurrentIndex(2)

        self.image_label.update()

    def toggle_crop_mode(self, enabled: bool):
        self.crop_mode_active = enabled
        if enabled:
            self.set_ui_mode("crop")
            self.crop_action.setText("✓ Disable Crop Mode")
            self.show_toast("Crop mode enabled")
        else:
            self.set_ui_mode("none")
            self.crop_action.setText("Enable Crop Mode")
            self.show_toast("Crop mode disabled")

    def handle_bbox_button(self, checked: bool):
        self.bbox_mode_active = checked
        if checked:
            self.set_ui_mode("bbox", None)
            self.bbox_action.setText("✓ Disable Bbox Mode")
            self.show_toast("Bbox mode enabled")
        else:
            self.set_ui_mode("none")
            self.bbox_action.setText("Enable Bbox Mode")
            self.show_toast("Bbox mode disabled")

    def toggle_crop_mode_action(self):
        self.crop_mode_active = not getattr(self, 'crop_mode_active', False)
        if self.crop_mode_active:
            self.crop_action.setText("✓ Disable Crop Mode")
            self.set_ui_mode("crop")
            self.show_toast("Crop mode enabled")
        else:
            self.crop_action.setText("Enable Crop Mode")
            self.set_ui_mode("none")
            self.show_toast("Crop mode disabled")

    def toggle_bbox_mode_action(self):
        self.bbox_mode_active = not getattr(self, 'bbox_mode_active', False)
        if self.bbox_mode_active:
            self.bbox_action.setText("✓ Disable Bbox Mode")
            self.set_ui_mode("bbox")
            self.show_toast("Bbox mode enabled")
        else:
            self.bbox_action.setText("Enable Bbox Mode")
            self.set_ui_mode("none")
            self.show_toast("Bbox mode disabled")

    def handle_export_json(self):
        if self.csv_path is None:
            self.show_toast("⚠ No CSV loaded")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            os.path.splitext(self.csv_path)[0] + ".json",
            "JSON Files (*.json)"
        )
        if not output_path:
            return

        result = export_to_json(
            csv_path=self.csv_path,
            questions_for_category=self.questions_for_category,
            output_path=output_path
        )

        if result:
            self.show_toast(f"JSON exported: {os.path.basename(result)}")
        else:
            self.show_toast("⚠ Export failed")

    # ------------------------------------------------------------------ #
    #  Questions                                                           #
    # ------------------------------------------------------------------ #

    def load_questions(self, filepath: str):
        if not os.path.exists(filepath):
            print(f"File {filepath} non trovato.")
            return

        for i in reversed(range(self.toolbox.count())):
            self.toolbox.removeItem(i)

        self.answer_widgets = {}
        self.questions_for_category = {}
        self.category_visibility_buttons = {}
        self.category_point_widgets = {}
        self.veil_buttons = []
        self.ring_volva_buttons = []

        categories = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split("||")
                if len(parts) != 2:
                    continue
                category, q_part = parts
                q_parts = q_part.split("|")
                if len(q_parts) >= 2:
                    question = q_parts[0]
                    options = q_parts[1:]
                    if category not in categories:
                        categories[category] = []
                    categories[category].append((question, options))

        self.color_map = {}
        for i, category in enumerate(categories.keys()):
            self.color_map[category] = self.category_colors[i % len(self.category_colors)]

        self.image_label.set_color_map(self.color_map)

        for category, qlist in categories.items():
            cat_widget = QWidget()
            cat_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            cat_layout = QVBoxLayout(cat_widget)

            # Titolo e pulsanti visibilità
            title_layout = QHBoxLayout()
            title_label = QLabel(f"<b>{category}</b>")
            title_layout.addWidget(title_label)
            title_layout.addStretch()

            visibility_group = QButtonGroup(self)
            visibility_group.setExclusive(True)

            def make_icon_button(icon_path, tooltip):
                btn = QPushButton()
                btn.setCheckable(True)
                btn.setToolTip(tooltip)
                btn.setFixedSize(48, 48)
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(40, 40))
                btn.setStyleSheet(self.button_style(normal=True))
                return btn

            eye_closed = make_icon_button(resource_path("ui_icons/eye-closed.png"), "Not Visible")
            eye_half   = make_icon_button(resource_path("ui_icons/eye-half.png"),   "Partially Visible")
            eye_open   = make_icon_button(resource_path("ui_icons/eye-open.png"),   "Fully Visible")

            visibility_group.addButton(eye_closed)
            visibility_group.addButton(eye_half)
            visibility_group.addButton(eye_open)
            visibility_group.setId(eye_closed, 0)
            visibility_group.setId(eye_half,   1)
            visibility_group.setId(eye_open,   2)
            visibility_group.buttonClicked.connect(
                lambda btn, cat=category: self.handle_visibility_button(cat, btn)
            )
            self.category_visibility_buttons[category] = [eye_closed, eye_half, eye_open]

            title_layout.addWidget(eye_closed)
            title_layout.addWidget(eye_half)
            title_layout.addWidget(eye_open)
            cat_layout.addLayout(title_layout)

            # Widget point mode
            point_mode_widget = QWidget()
            point_mode_layout = QVBoxLayout(point_mode_widget)
            point_mode_label = QLabel("<b>Point Mode</b>: Inactive")
            coordinates_label = QLabel("Coordinates: (n/a, n/a)")
            point_mode_layout.addWidget(point_mode_label)
            point_mode_layout.addWidget(coordinates_label)
            point_mode_widget.hide()
            cat_layout.addWidget(point_mode_widget)
            self.category_point_widgets[category] = {
                "widget": point_mode_widget,
                "mode_label": point_mode_label,
                "coords_label": coordinates_label
            }

            # Gruppi di domande
            gruppi_categoria = []
            domande_categoria = []
            for question, options in qlist:
                group_box = QGroupBox(question)
                layout = QGridLayout()
                button_group = QButtonGroup(self)
                button_group.setExclusive(False)

                for idx, option in enumerate(options):
                    btn = QPushButton()
                    btn.setCheckable(True)
                    btn.setToolTip(option)
                    icon_path = resource_path(os.path.join('imgs', option + '.png'))
                    btn.setIcon(QIcon(icon_path))
                    btn.setIconSize(QSize(64, 64))
                    btn.setFixedSize(75, 75)
                    btn.setStyleSheet(self.button_style(normal=True))
                    btn.clicked.connect(
                        lambda _, b=btn, g=button_group: self.update_button_styles_group(b, g)
                    )

                    if category == "Veil":
                        btn.clicked.connect(self.update_ring_volva_state)
                        self.veil_buttons.append(btn)
                    elif category in ("Ring", "Volva"):
                        self.ring_volva_buttons.append(btn)

                    row = idx // 4
                    col = idx % 4
                    layout.addWidget(btn, row, col)
                    button_group.addButton(btn)

                button_group.buttonPressed.connect(
                    lambda btn, g=button_group: self.on_button_pressed(btn, g)
                )
                button_group.buttonClicked.connect(
                    lambda btn, g=button_group, c=category: self.on_button_clicked(btn, g, c)
                )

                group_box.setLayout(layout)
                cat_layout.addWidget(group_box)
                gruppi_categoria.append(button_group)
                domande_categoria.append((question, options))

            self.toolbox.addItem(cat_widget, category)
            self.answer_widgets[category] = gruppi_categoria
            self.questions_for_category[category] = domande_categoria

        self.update_ring_volva_state()

    # ------------------------------------------------------------------ #
    #  Visibility                                                          #
    # ------------------------------------------------------------------ #

    def handle_visibility_button(self, category: str, button):
        self.image_label.set_point_mode(False)

        if button.toolTip() == "Not Visible":
            for group in self.answer_widgets.get(category, []):
                group.setExclusive(False)
                for btn in group.buttons():
                    btn.setEnabled(False)
                    btn.setChecked(False)
                    btn.setStyleSheet(self.button_style(disabled=True))
                group.setExclusive(True)

            if category in self.image_label._points:
                del self.image_label._points[category]

            self.set_ui_mode("none")
            self.image_label.update()
        else:
            for group in self.answer_widgets.get(category, []):
                for btn in group.buttons():
                    btn.setEnabled(True)
                    if not btn.isChecked():
                        btn.setStyleSheet(self.button_style(normal=True))
                    else:
                        btn.setStyleSheet(self.button_style(selected=True))

            point_widgets = self.category_point_widgets[category]
            self.set_ui_mode("point", category)

            if category in self.image_label._points:
                point = self.image_label._points[category]
                x, y = int(point['x']), int(point['y'])
                point_widgets["coords_label"].setText(f"Coordinates: ({x}, {y})")
                self.image_label.update()
            else:
                point_widgets["coords_label"].setText(
                    "Click on the image to set the point"
                )

    def update_ring_volva_state(self):
        veil_true_selected = any(
            btn.isChecked() and btn.toolTip() == "True"
            for btn in self.veil_buttons
        )
        for btn in self.ring_volva_buttons:
            if veil_true_selected:
                btn.setChecked(False)
            btn.setEnabled(not veil_true_selected)
            btn.setStyleSheet(self.button_style(disabled=veil_true_selected))

    # ------------------------------------------------------------------ #
    #  Button styles                                                       #
    # ------------------------------------------------------------------ #

    def button_style(self, selected=False, disabled=False, normal=False) -> str:
        if normal:
            return """
                QPushButton {
                    border: 2px solid gray;
                    border-radius: 10px;
                    background-color: white;
                    font-family: "Segoe UI", sans-serif;
                }
                QPushButton:checked {
                    border: 3px solid #007ACC;
                    background-color: #e6f2ff;
                }
            """
        elif disabled:
            return """
                QPushButton {
                    border: 2px solid gray;
                    border-radius: 10px;
                    background-color: lightgray;
                    font-family: "Segoe UI", sans-serif;
                }
            """
        elif selected:
            return """
                QPushButton {
                    border: 3px solid #007ACC;
                    border-radius: 10px;
                    background-color: #cce6ff;
                    font-family: "Segoe UI", sans-serif;
                }
            """
        return ""

    def update_button_styles_group(self, clicked_btn, group):
        if clicked_btn and clicked_btn.isChecked():
            for btn in group.buttons():
                if btn == clicked_btn and btn.isChecked():
                    btn.setStyleSheet(self.button_style(selected=True))
                else:
                    btn.setStyleSheet(self.button_style(disabled=True))
        else:
            for btn in group.buttons():
                btn.setStyleSheet(self.button_style(normal=True))

    def on_button_pressed(self, button, group):
        if button.isChecked():
            group.setExclusive(False)

    def on_button_clicked(self, btn, group, category: str):
        group.setExclusive(True)
        self.update_button_styles_group(btn, group)
        if category == "Veil":
            self.update_ring_volva_state()

    # ------------------------------------------------------------------ #
    #  Toast notification                                                  #
    # ------------------------------------------------------------------ #

    def show_toast(self, message: str, duration: int = 1000):
        toast = QLabel(message, self)
        toast.setStyleSheet("""
            QLabel {
                background-color: #323232;
                color: #eee;
                padding: 12px 24px;
                border-radius: 12px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        toast.setGraphicsEffect(shadow)

        x = (self.width() - toast.width()) // 2
        y = self.height() - toast.height() - 30
        toast.move(x, y)

        effect = QGraphicsOpacityEffect()
        toast.setGraphicsEffect(effect)
        toast.show()

        self.fade_in = QPropertyAnimation(effect, b"opacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.start()

        def start_fade_out():
            self.fade_out = QPropertyAnimation(effect, b"opacity")
            self.fade_out.setDuration(500)
            self.fade_out.setStartValue(1.0)
            self.fade_out.setEndValue(0.0)
            self.fade_out.finished.connect(toast.deleteLater)
            self.fade_out.start()

        QTimer.singleShot(duration, start_fade_out)

    # ------------------------------------------------------------------ #
    #  Folder & CSV loading                                                #
    # ------------------------------------------------------------------ #

    def load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if not folder:
            return

        self.folder_path = folder
        self.image_list = sorted([
            f for f in os.listdir(folder)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))
        ])
        self.list_widget.clear()

        parent_folder = os.path.dirname(folder)

        # Chiedi all'utente cosa vuole fare con il CSV
        msg = QMessageBox(self)
        msg.setWindowTitle("CSV File")
        msg.setText("Do you have an existing CSV file for this dataset?")
        msg.setInformativeText("You can load an existing one, create a new one, or continue without CSV (annotations won't be saved).")
        btn_load   = msg.addButton("Load existing CSV",   QMessageBox.AcceptRole)
        btn_create = msg.addButton("Create new CSV",       QMessageBox.ActionRole)
        btn_skip   = msg.addButton("Continue without CSV", QMessageBox.RejectRole)
        msg.exec_()

        clicked = msg.clickedButton()

        if clicked == btn_load:
            # Flusso esistente
            csv_path_dialog, _ = QFileDialog.getOpenFileName(
                self, "Select CSV file", parent_folder, "CSV Files (*.csv)"
            )
            if not csv_path_dialog:
                self.csv_info_label.setText("⚠ No CSV loaded")
                self.csv_data = None
                self.cropped_csv_data = None
                if self.image_list:
                    self.update_image_list_display()
                    self.display_image(0)
                return

            self.csv_path = csv_path_dialog
            self.csv_data = load_csv(self.csv_path)

        elif clicked == btn_create:
            # Crea nuovo CSV con solo la colonna filename
            folder_name = os.path.basename(folder)
            csv_name = f"{folder_name}_annotations.csv"
            csv_path_new = os.path.join(parent_folder, csv_name)

            if os.path.exists(csv_path_new):
                # Se esiste già chiedi conferma prima di sovrascrivere
                confirm = QMessageBox.question(
                    self,
                    "File already exists",
                    f"{csv_name} already exists. Load it instead of creating a new one?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if confirm == QMessageBox.Yes:
                    self.csv_path = csv_path_new
                    self.csv_data = load_csv(self.csv_path)
                else:
                    import pandas as pd
                    df = pd.DataFrame({"filename": self.image_list})
                    df.to_csv(csv_path_new, index=False)
                    self.csv_path = csv_path_new
                    self.csv_data = load_csv(self.csv_path)
                    self.show_toast(f"Created: {csv_name}")
            else:
                import pandas as pd
                df = pd.DataFrame({"filename": self.image_list})
                df.to_csv(csv_path_new, index=False)
                self.csv_path = csv_path_new
                self.csv_data = load_csv(self.csv_path)
                self.show_toast(f"Created: {csv_name}")

        else:
            # Nessun CSV
            self.csv_info_label.setText("⚠ No CSV loaded")
            self.csv_data = None
            self.cropped_csv_data = None
            if self.image_list:
                self.update_image_list_display()
                self.display_image(0)
            return

        self.csv_data = load_csv(self.csv_path)

        if self.csv_data is None:
            self.csv_info_label.setText("⚠ No CSV loaded")
        else:
            updated_df = sync_csv_with_folder(self.csv_data, self.image_list)
            if len(updated_df) > len(self.csv_data):
                updated_df.to_csv(self.csv_path, index=False)
                self.csv_data = updated_df
                self.show_toast(f"Added {len(updated_df) - len(self.csv_data)} new images to CSV")
            self.csv_info_label.setText("✅ CSV uploaded successfully")

        # Salva i percorsi nel config
        config = load_config()
        config["images_path"] = folder
        config["csv_path"] = self.csv_path
        save_config(config)

        self.update_image_list_display()

        species_name = get_species_name(self.csv_data)
        self.cropped_csv_data = load_cropped_csv(folder, species_name)

        if self.image_list:
            first_unanswered = 0
            for i, img_name in enumerate(self.image_list):
                if not self.is_answered(img_name):
                    first_unanswered = i
                    break
            self.display_image(first_unanswered)

    # ------------------------------------------------------------------ #
    #  Image display & navigation                                          #
    # ------------------------------------------------------------------ #

    def display_image(self, index: int):
        if not (0 <= index < len(self.image_list)):
            return

        self.current_index = index
        self.image_label._crop_counter = 0
        self.image_label._bboxes = []
        self.image_label._current_bbox = None
        self._current_category = None
        self._points = {}
        self.image_label._points = {}
        self.image_label.update()

        for cat_widget in self.category_point_widgets.values():
            cat_widget["coords_label"].setText("Coordinates: (n/a, n/a)")
            cat_widget["mode_label"].setText("<b>Point Mode</b>: Inactive")

        file_name = self.image_list[index]
        self.list_widget.setCurrentRow(index)
        path = os.path.join(self.folder_path, file_name)

        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap)
            self.image_label.set_image_path(path)
        else:
            self.image_label.setText("Invalid image")

        self.reset_all_answers()
        self.update_ring_volva_state()
        self.load_previous_answers()
        self.update_csv_table(file_name)

        if self.crop_mode:
            self.load_existing_bboxes()
        self.update_image_counter()

    def update_image_list_display(self):
        self.list_widget.clear()
        for image_name in self.get_filtered_images():
            item = QListWidgetItem()
            answered = self.is_answered(image_name)

            # Thumbnail
            img_path = os.path.join(self.folder_path, image_name)
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(
                    48, 48,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                item.setIcon(QIcon(pixmap))

            # Testo con icona ✅ se annotata
            if answered:
                item.setText(f"✅ {image_name}")
            else:
                item.setText(image_name)

            self.list_widget.addItem(item)
        self.update_progress()

    def apply_filter(self, mode: str):
        # Aggiorna stato bottoni filtro
        self.filter_all_btn.setChecked(mode == "all")
        self.filter_unanswered_btn.setChecked(mode == "unanswered")
        self.filter_answered_btn.setChecked(mode == "answered")
        self.current_filter = mode
        self.update_image_list_display()
    
    def apply_search(self, text: str):
        self.update_image_list_display()

    def get_filtered_images(self) -> list:
        mode = getattr(self, 'current_filter', 'all')
        search = getattr(self, 'search_bar', None)
        query = search.text().strip().lower() if search else ""

        if mode == "answered":
            filtered = [img for img in self.image_list if self.is_answered(img)]
        elif mode == "unanswered":
            filtered = [img for img in self.image_list if not self.is_answered(img)]
        else:
            filtered = self.image_list

        if query:
            filtered = [img for img in filtered if query in img.lower()]

        return filtered
    
    def update_progress(self):
        if not self.image_list or self.csv_data is None:
            self.progress_bar.setMaximum(1)
            self.progress_bar.setValue(0)
            self.stat_total_label.setText("Total images: 0")
            self.stat_answered_label.setText("Annotated: 0")
            self.stat_missing_label.setText("Not annotated: 0")
            self.stat_session_label.setText("Annotated this session: 0")
            return

        total = len(self.image_list)
        answered = sum(1 for img in self.image_list if self.is_answered(img))
        missing = total - answered

        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(answered)
        self.stat_total_label.setText(f"Total images: {total}")
        self.stat_answered_label.setText(f"Annotated: {answered}")
        self.stat_missing_label.setText(f"Not annotated: {missing}")
        self.stat_session_label.setText(f"Annotated this session: {self.session_count}")

    def update_image_counter(self):
        if not self.image_list or self.current_index < 0:
            self.image_counter_label.setText("No image loaded")
            return

        total = len(self.image_list)
        current = self.current_index + 1
        image_name = self.image_list[self.current_index]
        self.image_counter_label.setText(
            f"Image {current} / {total}  —  {image_name}"
        )

    def jump_to_first_unanswered(self):
        if not self.image_list or self.csv_data is None:
            self.show_toast("⚠ No CSV loaded")
            return

        for i, img_name in enumerate(self.image_list):
            if not self.is_answered(img_name):
                self.display_image(i)
                self.show_toast(f"Jumped to: {img_name}")
                return

        self.show_toast("✅ All images annotated!")

    def on_item_clicked(self, item):
        # Recupera il nome reale dell'immagine rimuovendo l'eventuale prefisso ✅
        image_name = item.text().replace("✅ ", "")
        if image_name in self.image_list:
            self.display_image(self.image_list.index(image_name))

    def prev_image(self):
        if self.current_index > 0:
            self.display_image(self.current_index - 1)

    def next_image(self):
        if self.current_index < len(self.image_list) - 1:
            self.display_image(self.current_index + 1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.next_image()
        elif event.key() == Qt.Key_Left:
            self.prev_image()

    # ------------------------------------------------------------------ #
    #  CSV table                                                           #
    # ------------------------------------------------------------------ #

    def update_csv_table(self, image_name: str):
        if self.csv_data is None or "filename" not in self.csv_data.columns:
            self.csv_table.setRowCount(0)
            return

        row = self.csv_data[self.csv_data["filename"] == image_name]
        if row.empty:
            self.csv_table.setRowCount(0)
            return

        row_data = row.iloc[0].to_dict()
        self.csv_table.setRowCount(len(row_data))
        for i, (key, value) in enumerate(row_data.items()):
            self.csv_table.setItem(i, 0, QTableWidgetItem(str(key)))
            self.csv_table.setItem(i, 1, QTableWidgetItem(str(value)))

    # ------------------------------------------------------------------ #
    #  Answers: save, load, reset                                          #
    # ------------------------------------------------------------------ #

    def save_answers(self):
        if not (0 <= self.current_index < len(self.image_list)):
            return

        image_name = self.image_list[self.current_index]

        # Chiedi conferma se l'immagine è già annotata
        if self.is_answered(image_name):
            confirm = QMessageBox.question(
                self,
                "Overwrite annotation",
                f"Image '{image_name}' is already annotated.\nDo you want to overwrite it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.No:
                return

        # Attributi
        all_attributes = []
        for category, gruppi in self.answer_widgets.items():
            for group, (question, options) in zip(gruppi, self.questions_for_category[category]):
                if len(options) == 2 and set(options) == {"True", "False"}:
                    selected_btn = next((b for b in group.buttons() if b.isChecked()), None)
                    value = 1 if selected_btn and selected_btn.toolTip() == "True" else 0
                    all_attributes.append(value)
                else:
                    temp = [0] * len(options)
                    selected_btn = next((b for b in group.buttons() if b.isChecked()), None)
                    if selected_btn:
                        idx = options.index(selected_btn.toolTip())
                        temp[idx] = 1
                    all_attributes.extend(temp)

        attributes_str = ",".join(map(str, all_attributes))

        # Visibilità
        all_visibility = []
        for category, buttons in self.category_visibility_buttons.items():
            vis_array = [0, 0, 0]
            selected_btn = next((b for b in buttons if b.isChecked()), None)
            if selected_btn:
                vis_array[buttons.index(selected_btn)] = 1
            all_visibility.extend(vis_array)

        visibility_str = ",".join(map(str, all_visibility))

        # Punti
        all_points = []
        for category in self.questions_for_category.keys():
            if category in self._points and self._points[category]:
                p = self._points[category]
                all_points.append(f"{int(p['x'])}:{int(p['y'])}")
            else:
                all_points.append("")

        points_str = "|".join(all_points)

        # Salva tramite csv_manager (include backup automatico)
        updated_df = save_annotations(
            csv_path=self.csv_path,
            image_name=image_name,
            attributes_str=attributes_str,
            visibility_str=visibility_str,
            points_str=points_str,
            df=self.csv_data.copy()
        )

        if updated_df is not None:
            self.csv_data = updated_df
            self.session_count += 1
            self.update_image_list_display()
            self.next_image()
            self.show_toast(f"Saved: {image_name}")
        else:
            self.show_toast("⚠ Error saving annotations")

    def load_previous_answers(self):
        if not (0 <= self.current_index < len(self.image_list)):
            return

        image_name = self.image_list[self.current_index]
        if self.csv_data is None or "filename" not in self.csv_data.columns:
            return

        row_df = self.csv_data.loc[self.csv_data["filename"] == image_name]
        if row_df.empty:
            return

        row = row_df.iloc[0]

        # 1) Visibilità
        vis_flags = {}
        if "visibility" in self.csv_data.columns and pd.notna(row["visibility"]):
            vis_str = str(row["visibility"]).strip()
            if vis_str:
                vis_vals = [v.strip() for v in vis_str.split(",")]
                idx_val = 0
                for category in self.questions_for_category.keys():
                    buttons = self.category_visibility_buttons.get(category, [])
                    slice_vals = vis_vals[idx_val: idx_val + 3]
                    if len(slice_vals) < 3:
                        slice_vals += ["0"] * (3 - len(slice_vals))
                    sel_idx = None
                    for i, val in enumerate(slice_vals):
                        btn = buttons[i]
                        checked = (val == "1")
                        btn.setChecked(checked)
                        btn.setStyleSheet(self.button_style(selected=checked, normal=not checked))
                        if checked:
                            sel_idx = i
                    vis_flags[category] = sel_idx
                    idx_val += 3

        # 2) Attributi
        if "attributes" in self.csv_data.columns and pd.notna(row["attributes"]):
            attr_str = str(row["attributes"]).strip()
            if attr_str:
                attr_vals = [v.strip() for v in attr_str.split(",")]
                idx_val = 0
                for category in self.questions_for_category.keys():
                    gruppi = self.answer_widgets.get(category, [])
                    visible = vis_flags.get(category, 0) != 0
                    for group, (question, options) in zip(gruppi, self.questions_for_category[category]):
                        if len(options) == 2 and set(options) == {"True", "False"}:
                            if idx_val < len(attr_vals):
                                selected_value = int(attr_vals[idx_val])
                                for btn in group.buttons():
                                    if visible:
                                        is_selected = (btn.toolTip() == "True") == (selected_value == 1)
                                        btn.setChecked(is_selected)
                                        btn.setStyleSheet(self.button_style(
                                            selected=is_selected, normal=not is_selected
                                        ))
                                        btn.setEnabled(False)
                                    else:
                                        btn.setChecked(False)
                                        btn.setStyleSheet(self.button_style(normal=True, disabled=True))
                                        btn.setEnabled(False)
                            idx_val += 1
                        else:
                            n = len(options)
                            if idx_val + n <= len(attr_vals):
                                for i, btn in enumerate(group.buttons()):
                                    if visible:
                                        selected = int(attr_vals[idx_val + i]) == 1
                                        btn.setChecked(selected)
                                        btn.setStyleSheet(self.button_style(
                                            selected=selected, normal=not selected
                                        ))
                                        btn.setEnabled(False)
                                    else:
                                        btn.setChecked(False)
                                        btn.setStyleSheet(self.button_style(normal=True, disabled=True))
                                        btn.setEnabled(False)
                            idx_val += n

        # 3) Punti
        if "parts" in self.csv_data.columns and pd.notna(row["parts"]):
            points_str = str(row["parts"]).strip()
            self._points = {}
            self.image_label._points = {}
            if points_str:
                per_category = points_str.split("|")
                categories = list(self.questions_for_category.keys())
                if len(per_category) < len(categories):
                    per_category += [""] * (len(categories) - len(per_category))
                for cat, coords_str in zip(categories, per_category):
                    coords_str = coords_str.strip()
                    if coords_str:
                        try:
                            x_str, y_str = coords_str.split(":")
                            x = float(x_str) if '.' in x_str else int(x_str)
                            y = float(y_str) if '.' in y_str else int(y_str)
                            self._points[cat] = {"x": x, "y": y}
                            self.image_label._points[cat] = {"x": x, "y": y}
                            if cat in self.category_point_widgets:
                                self.category_point_widgets[cat]["coords_label"].setText(
                                    f"Coordinates: ({int(x)},{int(y)})"
                                )
                        except Exception:
                            pass
                    else:
                        if cat in self.category_point_widgets:
                            self.category_point_widgets[cat]["coords_label"].setText(
                                "Coordinates: (n/a, n/a)"
                            )
            self.image_label.update()

    def reset_all_answers(self):
        for gruppi in self.answer_widgets.values():
            for group in gruppi:
                for btn in group.buttons():
                    btn.setChecked(False)
                    btn.setStyleSheet(self.button_style(normal=True))
                    btn.setEnabled(True)

        for btn_list in self.category_visibility_buttons.values():
            for btn in btn_list:
                btn.setChecked(False)
                btn.setStyleSheet(self.button_style(normal=True))
                btn.setEnabled(True)

    def is_answered(self, image_name: str) -> bool:
        if self.csv_data is None:
            return False
        if "attributes" not in self.csv_data.columns:
            return False
        row = self.csv_data.loc[self.csv_data["filename"] == image_name]
        if row.empty:
            return False
        value = str(row.iloc[0]["attributes"]).strip().lower()
        return value != "" and value != "nan"

    def update_coordinates_label(self, x: int, y: int, category: str):
        if category in self.category_point_widgets:
            self.category_point_widgets[category]["coords_label"].setText(
                f"Coordinates: ({x}, {y})"
            )
        self._points[category] = {'x': x, 'y': y}

    # ------------------------------------------------------------------ #
    #  Bbox                                                                #
    # ------------------------------------------------------------------ #

    def update_bbox_coordinates_label(self, bbox):
        if bbox:
            self.bbox_coordinates_label.setText(
                f"Coordinates: {bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}"
            )
        else:
            self.bbox_coordinates_label.setText("Coordinates: (n/a, n/a)")

    def submit_current_bbox(self):
        bbox = self.image_label.get_current_bbox()
        if not bbox:
            self.show_toast("No bbox to save!")
            return
        if self.csv_path is None:
            self.show_toast("⚠ No CSV loaded")
            return

        try:
            df = pd.read_csv(self.csv_path)
            img_name = self.image_list[self.current_index]
            if img_name not in df['filename'].values:
                self.show_toast(f"No row found for {img_name}")
                return

            df.loc[df['filename'] == img_name, 'bbox_mush_xmin'] = bbox[0]
            df.loc[df['filename'] == img_name, 'bbox_mush_ymin'] = bbox[1]
            df.loc[df['filename'] == img_name, 'bbox_mush_xmax'] = bbox[2]
            df.loc[df['filename'] == img_name, 'bbox_mush_ymax'] = bbox[3]
            df.to_csv(self.csv_path, index=False)
            self.csv_data = df
            self.show_toast(f"Bbox saved for: {img_name}")
        except Exception as e:
            print(f"Error saving bbox: {e}")

    def load_existing_bboxes(self):
        if not (0 <= self.current_index < len(self.image_list)):
            return
        if self.cropped_csv_data is None:
            self.image_label._bboxes = []
            self.image_label.update()
            return

        current_img = self.image_list[self.current_index]
        if "source_filename" not in self.cropped_csv_data.columns:
            self.image_label._bboxes = []
            self.image_label.update()
            return

        row = self.cropped_csv_data[self.cropped_csv_data["source_filename"] == current_img]
        bboxes = []
        needed = ["bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax"]
        if not row.empty and all(c in row.columns for c in needed):
            for _, r in row.iterrows():
                try:
                    x1, y1 = int(r["bbox_xmin"]), int(r["bbox_ymin"])
                    x2, y2 = int(r["bbox_xmax"]), int(r["bbox_ymax"])
                    if (x2 - x1) > 0 and (y2 - y1) > 0:
                        bboxes.append((x1, y1, x2, y2))
                except Exception:
                    pass

        self.image_label._bboxes = bboxes
        self.image_label.update()

    # ------------------------------------------------------------------ #
    #  Crop                                                                #
    # ------------------------------------------------------------------ #

    def add_crop_to_csv(self, original_path, crop_name, cropped_pixmap, bbox):
        if self.csv_path is None:
            return
        try:
            df = pd.read_csv(self.csv_path)
            original_name = os.path.basename(original_path)
            matching_row = df[df["filename"] == original_name]
            if matching_row.empty:
                return

            new_row = matching_row.iloc[0].copy()
            species_name = str(new_row.get("species", "unknown")).replace(" ", "_")
            crop_dir = os.path.join(os.path.dirname(self.folder_path), f"{species_name}_cropped")
            os.makedirs(crop_dir, exist_ok=True)

            base_name = os.path.splitext(original_name)[0]
            crop_index = get_next_crop_index(crop_dir, base_name)
            crop_name = f"{base_name}_{crop_index}.jpg"
            new_row["filename"] = crop_name
            new_row["bbox_xmin"] = bbox[0]
            new_row["bbox_ymin"] = bbox[1]
            new_row["bbox_xmax"] = bbox[2]
            new_row["bbox_ymax"] = bbox[3]
            new_row["source_filename"] = original_name

            cropped_pixmap.save(os.path.join(crop_dir, crop_name))

            cropped_csv_path = os.path.join(
                os.path.dirname(self.folder_path), f"{species_name}_cropped.csv"
            )
            if os.path.exists(cropped_csv_path):
                df_existing = pd.read_csv(cropped_csv_path)
                df_new = pd.concat([df_existing, pd.DataFrame([new_row])], ignore_index=True)
            else:
                df_new = pd.DataFrame([new_row])

            df_new.to_csv(cropped_csv_path, index=False)
            self.cropped_csv_data = df_new

        except Exception as e:
            print(f"Error updating CSV: {e}")

    def move_image_to_cropped(self):
        if not (0 <= self.current_index < len(self.image_list)):
            return
        if self.csv_path is None:
            return
        try:
            from shutil import copy2
            df = pd.read_csv(self.csv_path)
            original_path = os.path.join(self.folder_path, self.image_list[self.current_index])
            original_name = os.path.basename(original_path)
            matching_row = df[df["filename"] == original_name]
            if matching_row.empty:
                return

            new_row = matching_row.iloc[0].copy()
            species_name = str(new_row.get("species", "unknown")).replace(" ", "_")
            crop_dir = os.path.join(os.path.dirname(self.folder_path), f"{species_name}_cropped")
            os.makedirs(crop_dir, exist_ok=True)

            new_name = os.path.basename(original_path)
            crop_path = os.path.join(crop_dir, new_name)
            pixmap = QPixmap(original_path)

            copy2(original_path, crop_path)

            new_row["filename"] = new_name
            new_row["bbox_xmin"] = new_row["bbox_ymin"] = 0
            new_row["bbox_xmax"] = pixmap.width()
            new_row["bbox_ymax"] = pixmap.height()
            new_row["source_filename"] = original_name

            cropped_csv_path = os.path.join(
                os.path.dirname(self.folder_path), f"{species_name}_cropped.csv"
            )
            if os.path.exists(cropped_csv_path):
                df_existing = pd.read_csv(cropped_csv_path)
                df_new = pd.concat([df_existing, pd.DataFrame([new_row])], ignore_index=True)
            else:
                df_new = pd.DataFrame([new_row])

            df_new.to_csv(cropped_csv_path, index=False)
            self.cropped_csv_data = df_new
            self.show_toast(f"Image copied to cropped: {new_name}")

        except Exception as e:
            print(f"Error moving image: {e}")


    def show_statistics_window(self):
        if self.csv_data is None:
            self.show_toast("⚠ No CSV loaded")
            return

        window = StatisticsWindow(
            csv_data=self.csv_data,
            questions_for_category=self.questions_for_category,
            parent=self
        )
        window.exec_()


    def handle_load_questions(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select questions file",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        if not filepath:
            return

        # Se c'è già un CSV caricato, chiedi conferma
        # perché cambiare le domande invalida le annotazioni esistenti
        if self.csv_data is not None:
            confirm = QMessageBox.question(
                self,
                "Change questions file",
                "Changing the questions file may make existing annotations inconsistent.\n"
                "Are you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.No:
                return

        self.load_questions(filepath)
        self.show_toast(f"Loaded: {os.path.basename(filepath)}")

        # Aggiorna il config con il nuovo percorso
        config = load_config()
        config["questions_path"] = filepath
        save_config(config)

        # Reset delle risposte se c'è un'immagine visualizzata
        if self.current_index >= 0:
            self.reset_all_answers()
            self.load_previous_answers()

    def toggle_theme(self):
        from qt_material import apply_stylesheet
        app = QApplication.instance()

        self.dark_theme = not getattr(self, 'dark_theme', False)

        if self.dark_theme:
            apply_stylesheet(app, theme='dark_teal.xml')
            self.theme_action.setText("Switch to Light Theme")
            qss_file = resource_path("style_dark.qss")
        else:
            apply_stylesheet(app, theme='light_teal_500.xml')
            self.theme_action.setText("Switch to Dark Theme")
            qss_file = resource_path("style.qss")

        try:
            with open(qss_file, "r") as f:
                app.setStyleSheet(app.styleSheet() + f.read())
        except Exception:
            pass