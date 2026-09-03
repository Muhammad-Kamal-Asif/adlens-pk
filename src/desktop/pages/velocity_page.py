"""Market Trend Velocity page for AdLens PK desktop app."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.analytics.trend_engine import get_market_pulse


class _CircularProgress(QWidget):
    """Simple circular progress indicator drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self.setMinimumSize(220, 220)
        self.setMaximumSize(220, 220)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, int(value)))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        side = min(width, height)
        pen_width = 18
        rect_size = side - pen_width - 20
        rect_x = (width - rect_size) / 2
        rect_y = (height - rect_size) / 2

        # Background arc
        bg_pen = QPen(QColor("#2d3148"))
        bg_pen.setWidth(pen_width)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(int(rect_x), int(rect_y), int(rect_size), int(rect_size), 0, 360 * 16)

        # Progress arc
        if self._value <= 33:
            color = QColor("#e63946")  # red
        elif self._value <= 66:
            color = QColor("#f59e0b")  # amber
        else:
            color = QColor("#10b981")  # green

        progress_pen = QPen(color)
        progress_pen.setWidth(pen_width)
        progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress_pen)
        span = int(-self._value * 3.6 * 16)
        painter.drawArc(int(rect_x), int(rect_y), int(rect_size), int(rect_size), 90 * 16, span)

        # Center text
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self._value}")


class TrendVelocityPage(QWidget):
    """
    Standalone Market Trend Velocity dashboard.
    Shows velocity score, industry movement, and emerging hooks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        header = QLabel("Market Trend Velocity")
        hf = QFont()
        hf.setPointSize(24)
        hf.setBold(True)
        header.setFont(hf)
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        sub = QLabel(
            "Week-over-week ad volume movement by industry, plus hook types that are gaining traction."
        )
        sub.setStyleSheet("color: #9ca3af; font-size: 14px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self._status_label = QLabel("Loading market pulse…")
        self._status_label.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(self._status_label)

        # Top row: circular score + three industry lists
        top_row = QHBoxLayout()
        top_row.setSpacing(24)

        # Circular progress card
        score_card = QFrame()
        score_card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border-radius: 10px;
                border-left: 3px solid #e63946;
                border-top: 1px solid #2d3148;
                border-right: 1px solid #2d3148;
                border-bottom: 1px solid #2d3148;
                padding: 16px;
            }
        """)
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(20, 20, 20, 20)
        score_layout.setSpacing(12)
        score_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        score_title = QLabel("Velocity Score")
        score_title.setStyleSheet(
            "color: #9ca3af; font-size: 14px; font-weight: 600; border: none; background: transparent;"
        )
        score_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(score_title)

        self._progress = _CircularProgress()
        score_layout.addWidget(self._progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self._score_caption = QLabel("Market activity index (0-100)")
        self._score_caption.setStyleSheet(
            "color: #6b7280; font-size: 12px; border: none; background: transparent;"
        )
        self._score_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self._score_caption)

        top_row.addWidget(score_card)

        # Industry lists
        lists_widget = QWidget()
        lists_layout = QHBoxLayout(lists_widget)
        lists_layout.setContentsMargins(0, 0, 0, 0)
        lists_layout.setSpacing(16)

        self._rising_list = self._build_industry_list("Rising Industries", "#10b981")
        self._stable_list = self._build_industry_list("Stable Industries", "#f59e0b")
        self._declining_list = self._build_industry_list("Declining Industries", "#e63946")

        lists_layout.addWidget(self._rising_list["widget"])
        lists_layout.addWidget(self._stable_list["widget"])
        lists_layout.addWidget(self._declining_list["widget"])

        top_row.addWidget(lists_widget, stretch=2)
        layout.addLayout(top_row)

        # Emerging hooks table
        hooks_title = QLabel("Emerging Hooks")
        htf = QFont()
        htf.setPointSize(16)
        htf.setBold(True)
        hooks_title.setFont(htf)
        hooks_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(hooks_title)

        self._hooks_table = QTableWidget(0, 4)
        self._hooks_table.setAlternatingRowColors(True)
        self._hooks_table.setStyleSheet(
            "QTableWidget { gridline-color: #2d3148; alternate-background-color: #1a1d27; } "
            "QHeaderView::section { background-color: #1e2130; color: #9ca3af; "
            "font-size: 11px; font-weight: 600; padding: 6px; border: none; }"
        )
        self._hooks_table.setHorizontalHeaderLabels(
            ["Hook Type", "Current %", "Historical %", "Change %"]
        )
        self._hooks_table.horizontalHeader().setStretchLastSection(True)
        self._hooks_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for col in (1, 2, 3):
            self._hooks_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._hooks_table.verticalHeader().setVisible(False)
        self._hooks_table.setFixedHeight(260)
        layout.addWidget(self._hooks_table)

        # Refresh button
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #d62828; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """)
        self._refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _build_industry_list(self, title: str, accent_color: str) -> dict:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border-radius: 10px;
                border-left: 3px solid #e63946;
                border-top: 1px solid #2d3148;
                border-right: 1px solid #2d3148;
                border-bottom: 1px solid #2d3148;
                padding: 16px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setStyleSheet(
            f"color: {accent_color}; font-size: 14px; font-weight: 600; border: none; background: transparent;"
        )
        layout.addWidget(label)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #161922;
                border: 1px solid #2d3148;
                border-radius: 8px;
                color: #ffffff;
                padding: 8px;
            }
            QListWidget::item {
                padding: 6px 4px;
                border-bottom: 1px solid #2d3148;
            }
            QListWidget::item:last { border-bottom: none; }
        """)
        list_widget.setFixedWidth(210)
        layout.addWidget(list_widget)

        return {"widget": card, "list": list_widget}

    def _populate_list(self, list_widget: QListWidget, items: list, color: str) -> None:
        list_widget.clear()
        if not items:
            item = QListWidgetItem("No data")
            item.setForeground(QColor("#6b7280"))
            list_widget.addItem(item)
            return

        for entry in items:
            industry = entry.get("industry", "Unknown")
            growth = entry.get("growth_pct", 0.0)
            sign = "+" if growth > 0 else ""
            text = f"{industry}  ({sign}{growth}%)"
            list_item = QListWidgetItem(text)
            list_item.setForeground(QColor(color))
            list_widget.addItem(list_item)

    def _populate_hooks_table(self, hooks: list) -> None:
        self._hooks_table.setRowCount(len(hooks))
        for row, hook in enumerate(hooks):
            items = [
                QTableWidgetItem(str(hook.get("hook_type", ""))),
                QTableWidgetItem(f"{hook.get('current_pct', 0.0)}%"),
                QTableWidgetItem(f"{hook.get('historical_pct', 0.0)}%"),
                QTableWidgetItem(f"{hook.get('change_pct', 0.0):+.2f}%"),
            ]
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:
                    change = hook.get("change_pct", 0.0)
                    if change > 0:
                        item.setForeground(QColor("#10b981"))
                    elif change < 0:
                        item.setForeground(QColor("#e63946"))
                self._hooks_table.setItem(row, col, item)

    def refresh(self) -> None:
        """Reload market pulse data and repaint all widgets."""
        self._refresh_btn.setEnabled(False)
        self._status_label.setText("Loading market pulse…")
        self._status_label.setStyleSheet("color: #9ca3af; font-size: 13px;")

        try:
            pulse = get_market_pulse()
            velocity = pulse.get("velocity", {})

            score = int(round(velocity.get("velocity_score", 0)))
            self._progress.set_value(score)

            self._populate_list(
                self._rising_list["list"],
                velocity.get("rising_industries", []),
                "#10b981",
            )
            self._populate_list(
                self._stable_list["list"],
                velocity.get("stable_industries", []),
                "#f59e0b",
            )
            self._populate_list(
                self._declining_list["list"],
                velocity.get("declining_industries", []),
                "#e63946",
            )
            self._populate_hooks_table(pulse.get("emerging_hooks", []))

            total = pulse.get("total_ads", 0)
            current = pulse.get("current_window_ads", 0)
            self._status_label.setText(
                f"Pulse loaded: {total} total ads · {current} in the last 7 days · "
                f"velocity score {score}/100"
            )
            self._status_label.setStyleSheet("color: #10b981; font-size: 13px;")
        except Exception as exc:
            self._status_label.setText(f"Failed to load market pulse: {exc}")
            self._status_label.setStyleSheet("color: #e63946; font-size: 13px;")
        finally:
            self._refresh_btn.setEnabled(True)
