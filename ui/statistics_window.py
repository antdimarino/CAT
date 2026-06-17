import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QWidget, QTabWidget, QPushButton, QFileDialog
)
from PyQt5.QtCore import Qt


class StatisticsWindow(QDialog):
    def __init__(self, csv_data: pd.DataFrame, questions_for_category: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Annotation Statistics")
        self.setGeometry(150, 150, 900, 650)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # Finestra di sola lettura: nessuna interazione possibile
        self.setWindowModality(Qt.ApplicationModal)

        self.csv_data = csv_data
        self.questions_for_category = questions_for_category

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Titolo
        title = QLabel("<h2>Annotation Statistics</h2>")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Tab widget: una tab per categoria
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        main_layout.addWidget(self.tab_widget)

        # Tab 1: panoramica generale
        self._add_overview_tab()

        # Tab per ogni categoria
        for category in self.questions_for_category.keys():
            self._add_category_tab(category)

        # Pulsante export
        export_btn = QPushButton("Export all charts as PNG")
        export_btn.clicked.connect(self.export_charts)
        main_layout.addWidget(export_btn)

    # ------------------------------------------------------------------ #
    #  Overview tab                                                        #
    # ------------------------------------------------------------------ #

    def _add_overview_tab(self):
        total = len(self.csv_data)
        answered = 0
        if "attributes" in self.csv_data.columns:
            answered = self.csv_data["attributes"].apply(
                lambda x: str(x).strip() not in ["", "nan"]
            ).sum()
        missing = total - answered

        fig, axes = plt.subplots(1, 2, figsize=(9, 4))
        fig.suptitle("General Overview", fontsize=13, fontweight="bold")

        # Pie chart annotate vs non annotate
        axes[0].pie(
            [answered, missing],
            labels=["Annotated", "Not annotated"],
            autopct="%1.1f%%",
            colors=["#4CAF50", "#F44336"],
            startangle=90
        )
        axes[0].set_title("Annotation Progress")

        # Visibilità media per categoria
        visibility_labels = ["Not Visible", "Partially Visible", "Fully Visible"]
        category_names = list(self.questions_for_category.keys())
        visibility_counts = {cat: [0, 0, 0] for cat in category_names}

        if "visibility" in self.csv_data.columns:
            for _, row in self.csv_data.iterrows():
                vis_str = str(row.get("visibility", "")).strip()
                if not vis_str or vis_str == "nan":
                    continue
                vis_vals = [v.strip() for v in vis_str.split(",")]
                idx = 0
                for cat in category_names:
                    slice_vals = vis_vals[idx: idx + 3]
                    idx += 3
                    for i, val in enumerate(slice_vals):
                        if val == "1":
                            visibility_counts[cat][i] += 1
                            break

        x = range(len(category_names))
        colors = ["#F44336", "#FF9800", "#4CAF50"]
        bottoms = [0] * len(category_names)
        for i, label in enumerate(visibility_labels):
            values = [visibility_counts[cat][i] for cat in category_names]
            axes[1].bar(x, values, bottom=bottoms, label=label, color=colors[i])
            bottoms = [b + v for b, v in zip(bottoms, values)]

        axes[1].set_xticks(list(x))
        axes[1].set_xticklabels(category_names, rotation=30, ha="right", fontsize=8)
        axes[1].set_title("Visibility per Category")
        axes[1].legend(fontsize=8)
        axes[1].set_ylabel("Images")

        fig.tight_layout()

        canvas = FigureCanvas(fig)
        scroll = self._wrap_in_scroll(canvas)
        self.tab_widget.addTab(scroll, "Overview")
        plt.close(fig)

    # ------------------------------------------------------------------ #
    #  Category tab                                                        #
    # ------------------------------------------------------------------ #

    def _add_category_tab(self, category: str):
        qlist = self.questions_for_category.get(category, [])
        if not qlist:
            return

        # Decodifica attributi per questa categoria
        all_questions = []
        for cat, questions in self.questions_for_category.items():
            for question, options in questions:
                all_questions.append({
                    "category": cat,
                    "question": question,
                    "options": options
                })

        # Calcola offset nel vettore attributi per questa categoria
        offset = 0
        cat_questions_with_offset = []
        for q in all_questions:
            options = q["options"]
            is_bool = len(options) == 2 and set(options) == {"True", "False"}
            n = 1 if is_bool else len(options)
            if q["category"] == category:
                cat_questions_with_offset.append({
                    "question": q["question"],
                    "options": options,
                    "offset": offset,
                    "is_bool": is_bool,
                    "n": n
                })
            offset += n

        # Conta le selezioni per ogni domanda
        question_counts = []
        if "attributes" in self.csv_data.columns:
            for q_info in cat_questions_with_offset:
                counts = {opt: 0 for opt in q_info["options"]}
                for _, row in self.csv_data.iterrows():
                    attr_str = str(row.get("attributes", "")).strip()
                    if not attr_str or attr_str == "nan":
                        continue
                    attr_vals = [v.strip() for v in attr_str.split(",")]
                    off = q_info["offset"]
                    if q_info["is_bool"]:
                        if off < len(attr_vals):
                            val = int(attr_vals[off])
                            selected = "True" if val == 1 else "False"
                            counts[selected] += 1
                    else:
                        n = q_info["n"]
                        if off + n <= len(attr_vals):
                            for i, opt in enumerate(q_info["options"]):
                                if off + i < len(attr_vals) and int(attr_vals[off + i]) == 1:
                                    counts[opt] += 1
                question_counts.append({
                    "question": q_info["question"],
                    "counts": counts
                })

        if not question_counts:
            tab = QLabel("No data available for this category.")
            tab.setAlignment(Qt.AlignCenter)
            self.tab_widget.addTab(tab, category)
            return

        # Crea i grafici
        n_plots = len(question_counts)
        fig, axes = plt.subplots(1, n_plots, figsize=(max(5 * n_plots, 7), 4))
        fig.suptitle(f"{category} — Attribute Distribution", fontsize=12, fontweight="bold")

        if n_plots == 1:
            axes = [axes]

        for ax, q_data in zip(axes, question_counts):
            labels = list(q_data["counts"].keys())
            values = list(q_data["counts"].values())
            colors = plt.cm.Set3.colors[:len(labels)]
            bars = ax.bar(labels, values, color=colors)
            ax.set_title(q_data["question"], fontsize=8, wrap=True)
            ax.set_ylabel("Count")
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
            for bar, val in zip(bars, values):
                if val > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.1,
                        str(val),
                        ha="center", va="bottom", fontsize=7
                    )

        fig.tight_layout()

        canvas = FigureCanvas(fig)
        scroll = self._wrap_in_scroll(canvas)
        self.tab_widget.addTab(scroll, category)
        plt.close(fig)

    # ------------------------------------------------------------------ #
    #  Helper                                                              #
    # ------------------------------------------------------------------ #

    def _wrap_in_scroll(self, widget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def export_charts(self):
        export_dir = QFileDialog.getExistingDirectory(
            self, "Select export folder"
        )
        if not export_dir:
            return

        # Overview
        self._export_overview_chart(export_dir)

        # Una chart per ogni categoria
        for category in self.questions_for_category.keys():
            self._export_category_chart(category, export_dir)

        # Mostra conferma
        done_label = QLabel(f"✅ Charts exported to: {export_dir}")
        done_label.setAlignment(Qt.AlignCenter)
        done_label.setStyleSheet("color: green; font-weight: bold;")
        self.layout().addWidget(done_label)

    def _export_overview_chart(self, export_dir: str):
        total = len(self.csv_data)
        answered = 0
        if "attributes" in self.csv_data.columns:
            answered = self.csv_data["attributes"].apply(
                lambda x: str(x).strip() not in ["", "nan"]
            ).sum()
        missing = total - answered

        fig, axes = plt.subplots(1, 2, figsize=(10, 5))
        fig.suptitle("General Overview", fontsize=13, fontweight="bold")

        axes[0].pie(
            [answered, missing],
            labels=["Annotated", "Not annotated"],
            autopct="%1.1f%%",
            colors=["#4CAF50", "#F44336"],
            startangle=90
        )
        axes[0].set_title("Annotation Progress")

        visibility_labels = ["Not Visible", "Partially Visible", "Fully Visible"]
        category_names = list(self.questions_for_category.keys())
        visibility_counts = {cat: [0, 0, 0] for cat in category_names}

        if "visibility" in self.csv_data.columns:
            for _, row in self.csv_data.iterrows():
                vis_str = str(row.get("visibility", "")).strip()
                if not vis_str or vis_str == "nan":
                    continue
                vis_vals = [v.strip() for v in vis_str.split(",")]
                idx = 0
                for cat in category_names:
                    slice_vals = vis_vals[idx: idx + 3]
                    idx += 3
                    for i, val in enumerate(slice_vals):
                        if val == "1":
                            visibility_counts[cat][i] += 1
                            break

        x = range(len(category_names))
        colors = ["#F44336", "#FF9800", "#4CAF50"]
        bottoms = [0] * len(category_names)
        for i, label in enumerate(visibility_labels):
            values = [visibility_counts[cat][i] for cat in category_names]
            axes[1].bar(x, values, bottom=bottoms, label=label, color=colors[i])
            bottoms = [b + v for b, v in zip(bottoms, values)]

        axes[1].set_xticks(list(x))
        axes[1].set_xticklabels(category_names, rotation=30, ha="right", fontsize=8)
        axes[1].set_title("Visibility per Category")
        axes[1].legend(fontsize=8)
        axes[1].set_ylabel("Images")

        fig.tight_layout()
        fig.savefig(f"{export_dir}/overview.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    def _export_category_chart(self, category: str, export_dir: str):
        qlist = self.questions_for_category.get(category, [])
        if not qlist:
            return

        all_questions = []
        for cat, questions in self.questions_for_category.items():
            for question, options in questions:
                all_questions.append({
                    "category": cat,
                    "question": question,
                    "options": options
                })

        offset = 0
        cat_questions_with_offset = []
        for q in all_questions:
            options = q["options"]
            is_bool = len(options) == 2 and set(options) == {"True", "False"}
            n = 1 if is_bool else len(options)
            if q["category"] == category:
                cat_questions_with_offset.append({
                    "question": q["question"],
                    "options": options,
                    "offset": offset,
                    "is_bool": is_bool,
                    "n": n
                })
            offset += n

        question_counts = []
        if "attributes" in self.csv_data.columns:
            for q_info in cat_questions_with_offset:
                counts = {opt: 0 for opt in q_info["options"]}
                for _, row in self.csv_data.iterrows():
                    attr_str = str(row.get("attributes", "")).strip()
                    if not attr_str or attr_str == "nan":
                        continue
                    attr_vals = [v.strip() for v in attr_str.split(",")]
                    off = q_info["offset"]
                    if q_info["is_bool"]:
                        if off < len(attr_vals):
                            val = int(attr_vals[off])
                            selected = "True" if val == 1 else "False"
                            counts[selected] += 1
                    else:
                        n = q_info["n"]
                        if off + n <= len(attr_vals):
                            for i, opt in enumerate(q_info["options"]):
                                if off + i < len(attr_vals) and int(attr_vals[off + i]) == 1:
                                    counts[opt] += 1
                question_counts.append({
                    "question": q_info["question"],
                    "counts": counts
                })

        if not question_counts:
            return

        n_plots = len(question_counts)
        fig, axes = plt.subplots(1, n_plots, figsize=(5 * n_plots, 5))
        fig.suptitle(f"{category} — Attribute Distribution", fontsize=12, fontweight="bold")

        if n_plots == 1:
            axes = [axes]

        for ax, q_data in zip(axes, question_counts):
            labels = list(q_data["counts"].keys())
            values = list(q_data["counts"].values())
            colors = plt.cm.Set3.colors[:len(labels)]
            bars = ax.bar(labels, values, color=colors)
            ax.set_title(q_data["question"], fontsize=8)
            ax.set_ylabel("Count")
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
            for bar, val in zip(bars, values):
                if val > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.1,
                        str(val),
                        ha="center", va="bottom", fontsize=7
                    )

        fig.tight_layout()
        safe_name = category.replace(" ", "_").replace("/", "_")
        fig.savefig(f"{export_dir}/{safe_name}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)