from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.db.repository import get_all_ads
from src.ml.predictor import AdPredictor


class GraderPage(QWidget):
    """
    Standalone Ad Copy Grader page.

    Lets a user paste ad copy, select an industry, toggle offer signals, and
    receive a 0-100 score with explanatory feedback based on Pakistani market
    winning patterns.
    """

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.predictor = AdPredictor()
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0f1117; }")
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)

        # 1. Header
        header = QLabel("Ad Copy Grader")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        # 2. Subtitle
        subtitle = QLabel("Score your ad copy against Pakistani market winners")
        subtitle.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(subtitle)

        # 3. Input section
        input_label = QLabel("Your Ad Copy")
        input_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 600;")
        layout.addWidget(input_label)

        self.copy_input = QTextEdit()
        self.copy_input.setPlaceholderText("Paste your ad copy here...")
        self.copy_input.setMinimumHeight(160)
        self.copy_input.setStyleSheet("""
            QTextEdit {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 1px solid #22c55e;
            }
        """)
        layout.addWidget(self.copy_input)

        # 4. Controls row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(16)

        self.industry_combo = QComboBox()
        self.industry_combo.addItems([
            "Fashion",
            "Electronics",
            "Food & Grocery",
            "Health & Beauty",
            "Real Estate",
            "Education",
            "Home & Living",
            "Kids & Baby",
            "General",
        ])
        self.industry_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 8px 12px;
                min-height: 20px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e2130;
                color: #ffffff;
                selection-background-color: #22c55e;
                border: 1px solid #2d3148;
            }
        """)
        controls_layout.addWidget(self.industry_combo)

        self.cod_checkbox = QCheckBox("Includes COD offer")
        self.cod_checkbox.setStyleSheet("color: #9ca3af; spacing: 8px;")
        controls_layout.addWidget(self.cod_checkbox)

        self.price_checkbox = QCheckBox("Mentions price")
        self.price_checkbox.setStyleSheet("color: #9ca3af; spacing: 8px;")
        controls_layout.addWidget(self.price_checkbox)

        controls_layout.addStretch()

        self.grade_button = QPushButton("Grade This Ad")
        self.grade_button.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.grade_button.clicked.connect(self._on_grade_clicked)
        controls_layout.addWidget(self.grade_button)

        layout.addLayout(controls_layout)

        # 5. Score display
        self.score_label = QLabel("--")
        score_font = QFont()
        score_font.setPointSize(48)
        score_font.setBold(True)
        self.score_label.setFont(score_font)
        self.score_label.setStyleSheet("color: #9ca3af;")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score_label)

        # 6. Label display
        self.grade_label = QLabel("Paste ad copy and click Grade")
        grade_label_font = QFont()
        grade_label_font.setPointSize(18)
        grade_label_font.setBold(True)
        self.grade_label.setFont(grade_label_font)
        self.grade_label.setStyleSheet("color: #9ca3af;")
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.grade_label)

        # 7. Feedback section
        feedback_title = QLabel("Why this score:")
        feedback_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(feedback_title)

        self.feedback_list = QListWidget()
        self.feedback_list.setStyleSheet("""
            QListWidget {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #24283b;
            }
        """)
        self.feedback_list.setMinimumHeight(180)
        layout.addWidget(self.feedback_list)

        # 8. Market context
        self.context_label = QLabel("")
        self.context_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)

        layout.addStretch()

    def _on_grade_clicked(self) -> None:
        """Grade the pasted ad copy and update the UI."""
        if not self.predictor.is_ready():
            QMessageBox.warning(
                self,
                "Model Not Available",
                "Train the model first from the ML Training tab.",
            )
            return

        ad_copy = self.copy_input.toPlainText().strip()
        if not ad_copy:
            self.score_label.setText("--")
            self.grade_label.setText("Enter ad copy to grade")
            self.grade_label.setStyleSheet("color: #9ca3af;")
            self.feedback_list.clear()
            return

        industry = self.industry_combo.currentText()
        has_cod = self.cod_checkbox.isChecked()
        mentions_price = self.price_checkbox.isChecked()

        result = self.predictor.predict(
            ad_copy=ad_copy,
            industry=industry,
            has_cod=has_cod,
            mentions_price=mentions_price,
        )

        score = int(result.get("score", 0))
        label = str(result.get("label", "Unknown"))
        feedback: List[str] = result.get("feedback", [])

        self.score_label.setText(f"{score}%")

        if score > 70:
            color = "#10b981"  # green
        elif score > 40:
            color = "#f59e0b"  # amber
        else:
            color = "#22c55e"  # red

        self.score_label.setStyleSheet(f"color: {color};")
        self.grade_label.setText(label)
        self.grade_label.setStyleSheet(f"color: {color};")

        self.feedback_list.clear()
        for item_text in feedback:
            list_item = QListWidgetItem(item_text)
            self.feedback_list.addItem(list_item)

        self._update_market_context(industry)

    def _update_market_context(self, industry: str) -> None:
        """Display market context for the selected industry from stored ads."""
        try:
            ads = get_all_ads()
            industry_ads = [
                ad for ad in ads
                if ad.get("industry", "").lower() == industry.lower()
            ]
            survivor_days = [
                int(ad.get("days_active", 0))
                for ad in industry_ads
                if int(ad.get("days_active", 0)) >= 30
            ]
            if survivor_days:
                avg_days = sum(survivor_days) / len(survivor_days)
                self.context_label.setText(
                    f"In {industry}, ads running 30+ days average {avg_days:.0f} days active in our database."
                )
            elif industry_ads:
                self.context_label.setText(
                    f"In {industry}, {len(industry_ads)} ads stored; longevity data is not yet recorded in the database."
                )
            else:
                self.context_label.setText(
                    f"In {industry}, no ads are currently stored in the database."
                )
        except Exception as exc:
            self.context_label.setText(f"Could not load market context: {exc}")
