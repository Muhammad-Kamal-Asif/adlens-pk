from typing import Any, Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.schemas import (
    RawAdRecord,
    OfferMatrixSummary,
    HookAnalysisReport,
    TacticalCreativeBrief,
)
from src.core.fetcher import fetch_ads
from src.core.extractor import build_offer_matrix
from src.core.classifier import analyze_hooks
from src.core.ai_engine import generate_tactical_brief
from src.core.kaggle_enricher import get_demand_context
from src.db.repository import get_all_ads, get_trend_data

import pandas as pd


class AdFetchWorker(QThread):
    """
    Background worker thread for fetching and analyzing ads without freezing the UI.
    Calls fetch_ads() from src.core.fetcher, evaluates pipeline metrics, and generates AI brief.
    """
    results_ready = pyqtSignal(list, object, object, object)
    error_occurred = pyqtSignal(str)
    work_finished = pyqtSignal()

    def __init__(self, industry: str, use_mock: bool) -> None:
        super().__init__()
        self.industry = industry
        self.use_mock = use_mock

    def run(self) -> None:
        try:
            ads = fetch_ads(industry=self.industry, use_mock=self.use_mock)
            offer_matrix = build_offer_matrix(ads)
            hook_report = analyze_hooks(ads)
            brief = generate_tactical_brief(
                niche=self.industry,
                hook_report=hook_report,
                offer_matrix=offer_matrix,
            )
            self.results_ready.emit(ads, offer_matrix, hook_report, brief)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.work_finished.emit()



class TrendDataWorker(QThread):
    """Background worker that loads DB stats and demand context for the Trend Tracker page."""

    data_ready = pyqtSignal(list, list, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, industry: str) -> None:
        super().__init__()
        self.industry = industry

    def run(self) -> None:
        try:
            all_ads = get_all_ads()
            trend_rows = get_trend_data()
            demand_text = get_demand_context(self.industry or "general")
            self.data_ready.emit(all_ads, trend_rows, demand_text)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class AdLensPKWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AdLens PK")
        self.setMinimumSize(1200, 850)
        self._worker: Optional[AdFetchWorker] = None
        self._trend_worker: Optional[TrendDataWorker] = None
        self._ads: List[RawAdRecord] = []
        self._offer_matrix: Optional[OfferMatrixSummary] = None
        self._hook_report: Optional[HookAnalysisReport] = None
        self._brief: Optional[TacticalCreativeBrief] = None
        self._apply_dark_theme()

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        main_layout.addWidget(self.sidebar)

        self.content_stack = self._build_content_stack()
        main_layout.addWidget(self.content_stack, 1)

    def _apply_dark_theme(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f1117"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e2130"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e2130"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#1e2130"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#e63946"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

        self.setStyleSheet("""
            QWidget {
                background-color: #0f1117;
                color: #ffffff;
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            }
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
                selection-background-color: #e63946;
                border: 1px solid #2d3148;
            }
            QCheckBox {
                color: #9ca3af;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #2d3148;
                background-color: #1e2130;
            }
            QCheckBox::indicator:checked {
                background-color: #e63946;
                border: 1px solid #e63946;
            }
            QPushButton {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2d3148;
            }
            QTableWidget {
                background-color: #1e2130;
                color: #ffffff;
                gridline-color: #2d3148;
                border: 1px solid #2d3148;
                border-radius: 8px;
                selection-background-color: #2d3148;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #24283b;
            }
            QHeaderView::section {
                background-color: #1a1d27;
                color: #9ca3af;
                padding: 10px 8px;
                font-weight: 600;
                border: 1px solid #2d3148;
            }
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
            QScrollBar:vertical {
                background: #1e2130;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2d3148;
                min-height: 20px;
                border-radius: 4px;
            }
        """)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color: #1a1d27; border-right: 1px solid #2d3148;")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("AdLens PK")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #ffffff; border: none;")
        layout.addWidget(title)

        subtitle = QLabel("Pakistani Digital Ad Intelligence Engine")
        subtitle.setStyleSheet("color: #9ca3af; font-size: 13px; border: none;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #e63946;")
        layout.addWidget(divider)

        industry_label = QLabel("Industry / Niche")
        industry_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 600; border: none;")
        layout.addWidget(industry_label)

        self.industry_combo = QComboBox()
        self.industry_options = [
            "Fashion",
            "Electronics",
            "Food & Grocery",
            "Health & Beauty",
            "Real Estate",
            "Education",
            "Home & Living",
            "Kids & Baby",
            "General",
        ]
        self.industry_combo.addItems(self.industry_options)
        self.industry_combo.currentTextChanged.connect(self._refresh_trend_tracker)
        layout.addWidget(self.industry_combo)

        self.demo_checkbox = QCheckBox("Use Local Dataset (Demo Mode)")
        self.demo_checkbox.setChecked(True)
        layout.addWidget(self.demo_checkbox)

        self.generate_button = QPushButton("Generate Report")
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #d62828;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.generate_button.clicked.connect(self._on_generate_clicked)
        layout.addWidget(self.generate_button)

        nav_divider = QWidget()
        nav_divider.setFixedHeight(1)
        nav_divider.setStyleSheet("background-color: #2d3148;")
        layout.addWidget(nav_divider)

        nav_label = QLabel("Views")
        nav_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 600; border: none;")
        layout.addWidget(nav_label)

        self.nav_buttons: list[QPushButton] = []
        self.page_names = [
            "Market Overview",
            "Offer Matrix",
            "Hook Psychology",
            "Strategy Playbook",
            "Trend Tracker",
        ]
        for index, name in enumerate(self.page_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        layout.addStretch()

        return sidebar

    def _create_metric_card(self, title: str, default_value: str, subtitle: str) -> Tuple[QFrame, QLabel]:
        """Creates a styled QFrame metric card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border: 1px solid #2d3148;
                border-radius: 12px;
                padding: 18px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 600; border: none; background: transparent;")

        val_label = QLabel(default_value)
        val_font = QFont()
        val_font.setPointSize(24)
        val_font.setBold(True)
        val_label.setFont(val_font)
        val_label.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        val_label.setWordWrap(True)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("color: #6b7280; font-size: 12px; border: none; background: transparent;")

        card_layout.addWidget(title_label)
        card_layout.addWidget(val_label)
        card_layout.addWidget(sub_label)

        return card, val_label

    def _build_market_overview_page(self) -> QWidget:
        """Constructs the Market Overview page featuring three metric cards as QFrame widgets."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header title
        header_label = QLabel("Market Overview")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        self.market_overview_status = QLabel(
            "Select an industry in the sidebar and click 'Generate Report' to analyze ad intelligence."
        )
        self.market_overview_status.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(self.market_overview_status)

        # Metric Cards Row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(18)

        card_total, self.val_total_ads = self._create_metric_card(
            "Total Ads", "-", "Total active ads extracted & evaluated"
        )
        card_cod, self.val_cod_rate = self._create_metric_card(
            "COD Adoption Rate", "-", "Cash on delivery commercial prevalence"
        )
        card_lang, self.val_dom_lang = self._create_metric_card(
            "Dominant Language", "-", "Primary vernacular ad copy language"
        )

        cards_layout.addWidget(card_total)
        cards_layout.addWidget(card_cod)
        cards_layout.addWidget(card_lang)

        layout.addLayout(cards_layout)
        layout.addStretch()
        return page

    def _build_hook_psychology_page(self) -> QWidget:
        """Constructs Page 2: Hook Psychology with Dominant Angle metric card and detailed hooks table."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        header_label = QLabel("Hook Psychology")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Categorization of creative opening hooks, psychological triggers, and languages.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        # 1. Metric card for Dominant Psychological Angle
        card_angle, self.val_dom_hook = self._create_metric_card(
            "Dominant Psychological Angle", "-", "Most prevalent consumer psychological angle"
        )
        layout.addWidget(card_angle)

        # Table header label
        table_title = QLabel("Extracted Ad Hooks & Classifications")
        table_title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 600; margin-top: 10px;")
        layout.addWidget(table_title)

        # 2. QTableWidget with specified columns
        self.hooks_table = QTableWidget()
        self.hooks_table.setColumnCount(4)
        self.hooks_table.setHorizontalHeaderLabels([
            "Page Name",
            "Hook Type",
            "Language",
            "Raw Hook (first 80 chars)",
        ])
        self.hooks_table.horizontalHeader().setStretchLastSection(True)
        self.hooks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.hooks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.hooks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.hooks_table.setColumnWidth(0, 200)
        self.hooks_table.setColumnWidth(1, 200)
        self.hooks_table.setColumnWidth(2, 120)
        self.hooks_table.verticalHeader().setVisible(False)
        self.hooks_table.setMinimumHeight(380)

        layout.addWidget(self.hooks_table, 1)
        return page

    def _build_strategy_playbook_page(self) -> QWidget:
        """Constructs Page 3: Strategy Playbook with Gemini AI brief card, copy hooks list, and export button."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header row with Export Button
        header_row = QHBoxLayout()
        header_layout = QVBoxLayout()
        
        header_label = QLabel("Strategy Playbook")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(header_label)

        sub_label = QLabel("AI-synthesized tactical creative brief & performance marketing playbook.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        header_layout.addWidget(sub_label)
        header_row.addLayout(header_layout)

        header_row.addStretch()

        self.export_button = QPushButton("Export Strategy (.txt)")
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e63946;
                border-color: #e63946;
            }
            QPushButton:disabled {
                background-color: #1a1d27;
                color: #4b5563;
                border-color: #2d3148;
            }
        """)
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export_strategy_clicked)
        header_row.addWidget(self.export_button)

        layout.addLayout(header_row)

        # Scrollable container for brief content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(18)

        # 1. Dark QFrame Card for Gemini AI Brief
        brief_card = QFrame()
        brief_card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border: 1px solid #2d3148;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        brief_layout = QVBoxLayout(brief_card)
        brief_layout.setSpacing(14)

        # Field: Target Niche
        niche_title = QLabel("Target Niche")
        niche_title.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 700; text-transform: uppercase;")
        self.val_brief_niche = QLabel("-")
        self.val_brief_niche.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 600;")
        brief_layout.addWidget(niche_title)
        brief_layout.addWidget(self.val_brief_niche)

        # Field: Market Whitespace
        ws_title = QLabel("Market Whitespace")
        ws_title.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 700; text-transform: uppercase;")
        self.val_brief_whitespace = QLabel("Run 'Generate Report' to uncover untapped creative gaps in Pakistani digital ads.")
        self.val_brief_whitespace.setStyleSheet("color: #ffffff; font-size: 14px; line-height: 1.4;")
        self.val_brief_whitespace.setWordWrap(True)
        brief_layout.addWidget(ws_title)
        brief_layout.addWidget(self.val_brief_whitespace)

        # Field: Recommended Angle
        angle_title = QLabel("Recommended Angle")
        angle_title.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 700; text-transform: uppercase;")
        self.val_brief_angle = QLabel("-")
        self.val_brief_angle.setStyleSheet("color: #ffffff; font-size: 14px;")
        self.val_brief_angle.setWordWrap(True)
        brief_layout.addWidget(angle_title)
        brief_layout.addWidget(self.val_brief_angle)

        # Field: Recommended Offer Structure
        offer_title = QLabel("Recommended Offer Structure")
        offer_title.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 700; text-transform: uppercase;")
        self.val_brief_offer = QLabel("-")
        self.val_brief_offer.setStyleSheet("color: #ffffff; font-size: 14px;")
        self.val_brief_offer.setWordWrap(True)
        brief_layout.addWidget(offer_title)
        brief_layout.addWidget(self.val_brief_offer)

        scroll_layout.addWidget(brief_card)

        # 2. Suggested Copy Hooks Section
        hooks_title = QLabel("Suggested Copy Hooks")
        hooks_title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 600; margin-top: 6px;")
        scroll_layout.addWidget(hooks_title)

        self.hooks_list_widget = QListWidget()
        self.hooks_list_widget.setMinimumHeight(180)
        scroll_layout.addWidget(self.hooks_list_widget)

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area, 1)

        return page

    def _build_scaffold_page(self, name: str) -> QWidget:
        """Builds a placeholder scaffold page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(name)
        label_font = QFont()
        label_font.setPointSize(24)
        label_font.setBold(True)
        label.setFont(label_font)
        label.setStyleSheet("color: #ffffff;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sublabel = QLabel(f"{name} content will appear here.")
        sublabel.setStyleSheet("color: #9ca3af; font-size: 14px; margin-top: 8px;")
        sublabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        page_layout.addWidget(label)
        page_layout.addWidget(sublabel)
        return page

    def _build_trend_tracker_page(self) -> QWidget:
        """Page 4 - Trend Tracker: metric cards, demand signal, daily ingestion table."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #0f1117; }")

        container = QWidget()
        scroll_area.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel("Trend Tracker")
        hf = QFont()
        hf.setPointSize(24)
        hf.setBold(True)
        header.setFont(hf)
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        sub = QLabel("Longitudinal Ad Intelligence & Market Trends")
        sub.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(18)
        card_db, self.trend_val_total_db = self._create_metric_card(
            "Total Ads in Database", "-", "All-time ingested ad records"
        )
        card_pages, self.trend_val_unique_pages = self._create_metric_card(
            "Unique Pages Seen", "-", "Distinct advertiser pages tracked"
        )
        card_ind, self.trend_val_most_active = self._create_metric_card(
            "Most Active Industry", "-", "Highest volume ingested category"
        )
        cards_row.addWidget(card_db)
        cards_row.addWidget(card_pages)
        cards_row.addWidget(card_ind)
        layout.addLayout(cards_row)

        demand_lbl = QLabel("Pakistan Market Demand Signal")
        demand_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 700;")
        layout.addWidget(demand_lbl)

        self.trend_demand_label = QLabel("Loading demand context...")
        self.trend_demand_label.setWordWrap(True)
        self.trend_demand_label.setStyleSheet(
            "background-color: #1e2130; border: 1px solid #2d3148;"
            " border-left: 3px solid #e63946; border-radius: 8px;"
            " color: #9ca3af; font-size: 13px; padding: 14px 16px;"
        )
        layout.addWidget(self.trend_demand_label)

        self.trend_warning_label = QLabel(
            "Trend data builds over time \u2014 run the app daily to see patterns emerge."
        )
        self.trend_warning_label.setWordWrap(True)
        self.trend_warning_label.setStyleSheet(
            "background-color: #1a1d27; border: 1px solid #f59e0b;"
            " border-radius: 8px; color: #f59e0b; font-size: 13px; padding: 12px 16px;"
        )
        self.trend_warning_label.setVisible(False)
        layout.addWidget(self.trend_warning_label)

        tbl_title = QLabel("Daily Ingestion History")
        tbl_title.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 700;")
        layout.addWidget(tbl_title)

        self.trend_table = QTableWidget(0, 3)
        self.trend_table.setHorizontalHeaderLabels(["Date", "Ads Pulled", "COD Adoption %"])
        self.trend_table.horizontalHeader().setStretchLastSection(True)
        self.trend_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self.trend_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        self.trend_table.verticalHeader().setVisible(False)
        self.trend_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.trend_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.trend_table.setAlternatingRowColors(True)
        self.trend_table.setColumnWidth(0, 160)
        self.trend_table.setColumnWidth(1, 130)
        self.trend_table.setMinimumHeight(260)
        layout.addWidget(self.trend_table)
        layout.addStretch()

        return scroll_area

    def _refresh_trend_tracker(self) -> None:
        if self._trend_worker is not None and self._trend_worker.isRunning():
            return
        industry = self.industry_combo.currentText()
        if hasattr(self, "trend_demand_label"):
            self.trend_demand_label.setText("Loading demand context...")
        if hasattr(self, "trend_warning_label"):
            self.trend_warning_label.setVisible(False)
        self._trend_worker = TrendDataWorker(industry=industry)
        self._trend_worker.data_ready.connect(self._on_trend_data_ready)
        self._trend_worker.error_occurred.connect(self._on_trend_data_error)
        self._trend_worker.start()

    def _on_trend_data_ready(
        self,
        all_ads: List[Dict[str, Any]],
        trend_rows: List[Dict[str, Any]],
        demand_text: str,
    ) -> None:
        total_db = len(all_ads)
        self.trend_val_total_db.setText(f"{total_db:,}")

        if all_ads:
            df = pd.DataFrame(all_ads)
            unique_pages = int(df["page_name"].nunique()) if "page_name" in df.columns else 0
            self.trend_val_unique_pages.setText(f"{unique_pages:,}")
            if "industry" in df.columns and not df["industry"].dropna().empty:
                most_active = str(df["industry"].value_counts().index[0]).title()
            else:
                most_active = "N/A"
            self.trend_val_most_active.setText(most_active)
        else:
            self.trend_val_unique_pages.setText("0")
            self.trend_val_most_active.setText("N/A")

        self.trend_demand_label.setText(demand_text)
        self.trend_demand_label.setStyleSheet(
            "background-color: #1e2130; border: 1px solid #2d3148;"
            " border-left: 3px solid #e63946; border-radius: 8px;"
            " color: #9ca3af; font-size: 13px; padding: 14px 16px;"
        )

        self.trend_warning_label.setVisible(len(trend_rows) <= 1)

        cod_by_date: Dict[str, float] = {}
        if all_ads:
            df_full = pd.DataFrame(all_ads)
            if "pulled_at" in df_full.columns and "has_cod" in df_full.columns:
                df_full["_date"] = (
                    pd.to_datetime(df_full["pulled_at"], errors="coerce")
                    .dt.date.astype(str)
                )
                cod_by_date = (
                    df_full.groupby("_date")["has_cod"]
                    .apply(lambda x: round(x.sum() / max(len(x), 1) * 100, 1))
                    .to_dict()
                )

        self.trend_table.setRowCount(0)
        for row_data in trend_rows:
            date_str = str(row_data.get("date", ""))
            ads_count = str(row_data.get("count", 0))
            cod_pct = cod_by_date.get(date_str)
            cod_str = f"{cod_pct:.1f}%" if cod_pct is not None else "N/A"
            row_idx = self.trend_table.rowCount()
            self.trend_table.insertRow(row_idx)
            for col, value in enumerate([date_str, ads_count, cod_str]):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                self.trend_table.setItem(row_idx, col, cell)

        if not trend_rows:
            self.trend_table.insertRow(0)
            placeholder = QTableWidgetItem("No data yet \u2014 generate a report first.")
            placeholder.setForeground(QColor("#6b7280"))
            self.trend_table.setItem(0, 0, placeholder)

    def _on_trend_data_error(self, error_msg: str) -> None:
        self.trend_demand_label.setText(f"Error loading trend data: {error_msg}")
        self.trend_demand_label.setStyleSheet(
            "background-color: #1e2130; border: 1px solid #e63946;"
            " border-left: 3px solid #e63946; border-radius: 8px;"
            " color: #e63946; font-size: 13px; padding: 14px 16px;"
        )

    def _build_content_stack(self) -> QStackedWidget:
        stack = QStackedWidget()
        stack.setStyleSheet("background-color: #0f1117;")

        # Page 0: Market Overview
        stack.addWidget(self._build_market_overview_page())

        # Page 1: Offer Matrix (Scaffold)
        stack.addWidget(self._build_scaffold_page("Offer Matrix"))

        # Page 2: Hook Psychology
        stack.addWidget(self._build_hook_psychology_page())

        # Page 3: Strategy Playbook
        stack.addWidget(self._build_strategy_playbook_page())

        # Page 4: Trend Tracker
        stack.addWidget(self._build_trend_tracker_page())

        # Kick off initial data load
        self._refresh_trend_tracker()

        return stack

    def _switch_page(self, index: int) -> None:
        self.content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 4:
            self._refresh_trend_tracker()

    def _on_generate_clicked(self) -> None:
        """Handles 'Generate Report' button click by dispatching work to QThread."""
        industry = self.industry_combo.currentText()
        use_mock = self.demo_checkbox.isChecked()

        self.generate_button.setEnabled(False)
        self.generate_button.setText("Analyzing...")
        self.market_overview_status.setText(f"Fetching and analyzing ad intelligence for '{industry}'...")
        self.market_overview_status.setStyleSheet("color: #9ca3af; font-size: 14px;")

        # Switch to Market Overview page
        self._switch_page(0)

        # Launch QThread worker
        self._worker = AdFetchWorker(industry=industry, use_mock=use_mock)
        self._worker.results_ready.connect(self._on_report_generated)
        self._worker.error_occurred.connect(self._on_report_error)
        self._worker.work_finished.connect(self._on_work_finished)
        self._worker.start()

    def _on_report_generated(
        self,
        ads: List[RawAdRecord],
        offer_matrix: OfferMatrixSummary,
        hook_report: HookAnalysisReport,
        brief: TacticalCreativeBrief,
    ) -> None:
        """Updates all pages with actual pipeline values and AI brief."""
        self._ads = ads
        self._offer_matrix = offer_matrix
        self._hook_report = hook_report
        self._brief = brief

        # 1. Update Market Overview
        total_ads = len(ads)
        cod_rate = f"{offer_matrix.cod_prevalence_pct:.1f}%"
        dom_lang = str(hook_report.dominant_language)

        self.val_total_ads.setText(f"{total_ads:,}")
        self.val_cod_rate.setText(cod_rate)
        self.val_dom_lang.setText(dom_lang)

        industry = self.industry_combo.currentText()
        mode_desc = "Local Demo Dataset" if self.demo_checkbox.isChecked() else "Live Meta API"
        self.market_overview_status.setText(
            f"Ad intelligence report successfully generated for '{industry}' ({mode_desc}). "
            f"Evaluated {total_ads} ads."
        )
        self.market_overview_status.setStyleSheet("color: #10b981; font-size: 14px;")

        # 2. Update Hook Psychology Page
        self.val_dom_hook.setText(str(hook_report.dominant_hook_type))
        self.hooks_table.setRowCount(0)
        for row_idx, item in enumerate(hook_report.items):
            self.hooks_table.insertRow(row_idx)
            raw_truncated = item.raw_hook[:80] + ("..." if len(item.raw_hook) > 80 else "")

            p_item = QTableWidgetItem(item.page_name)
            h_item = QTableWidgetItem(item.hook_type)
            l_item = QTableWidgetItem(item.language)
            r_item = QTableWidgetItem(raw_truncated)

            for cell in (p_item, h_item, l_item, r_item):
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.hooks_table.setItem(row_idx, 0, p_item)
            self.hooks_table.setItem(row_idx, 1, h_item)
            self.hooks_table.setItem(row_idx, 2, l_item)
            self.hooks_table.setItem(row_idx, 3, r_item)

        # 3. Update Strategy Playbook Page
        self.val_brief_niche.setText(brief.target_niche)
        self.val_brief_whitespace.setText(brief.market_whitespace)
        self.val_brief_angle.setText(brief.recommended_angle)
        self.val_brief_offer.setText(brief.recommended_offer_structure)

        self.hooks_list_widget.clear()
        for idx, hook_text in enumerate(brief.suggested_hooks, start=1):
            list_item = QListWidgetItem(f"Hook #{idx}: {hook_text}")
            self.hooks_list_widget.addItem(list_item)

        self.export_button.setEnabled(True)

    def _on_export_strategy_clicked(self) -> None:
        """Exports the current AI strategy brief to a text file using QFileDialog."""
        if not self._brief:
            return

        industry_name = self.industry_combo.currentText().lower().replace(" ", "_")
        default_filename = f"adlens_strategy_{industry_name}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Strategy (.txt)",
            default_filename,
            "Text Files (*.txt);;All Files (*)",
        )

        if not file_path:
            return

        hooks_text = "\n".join(
            f"  {idx}. {h}" for idx, h in enumerate(self._brief.suggested_hooks, start=1)
        )
        content = (
            "======================================================================\n"
            "AdLens PK — Tactical Campaign Strategy Brief\n"
            f"Target Niche: {self._brief.target_niche}\n"
            "======================================================================\n\n"
            "1. TARGET NICHE\n"
            f"   {self._brief.target_niche}\n\n"
            "2. MARKET WHITESPACE\n"
            f"   {self._brief.market_whitespace}\n\n"
            "3. RECOMMENDED PSYCHOLOGICAL ANGLE\n"
            f"   {self._brief.recommended_angle}\n\n"
            "4. RECOMMENDED OFFER STRUCTURE\n"
            f"   {self._brief.recommended_offer_structure}\n\n"
            "5. SUGGESTED COPY HOOKS\n"
            f"{hooks_text}\n\n"
            "======================================================================\n"
            "Generated by AdLens PK Engine\n"
            "======================================================================\n"
        )

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:
            self.market_overview_status.setText(f"Export failed: {exc}")
            self.market_overview_status.setStyleSheet("color: #e63946; font-size: 14px;")

    def _on_report_error(self, error_msg: str) -> None:
        """Handles pipeline worker failure."""
        self.market_overview_status.setText(f"Error generating report: {error_msg}")
        self.market_overview_status.setStyleSheet("color: #e63946; font-size: 14px;")

    def _on_work_finished(self) -> None:
        """Restores button state once worker finishes."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Report")


if __name__ == "__main__":
    app = QApplication([])
    window = AdLensPKWindow()
    window.show()
    app.exec()
