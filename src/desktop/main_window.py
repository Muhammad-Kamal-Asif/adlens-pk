import os
import sys
from collections import Counter
from typing import List, Optional, Tuple, Dict, Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QDateTime
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
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
from src.core.exporter import export_report_pdf
from src.db.watchlist import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    update_watchlist_stats,
)
from src.db.repository import init_db


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


class AdLensPKWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AdLens PK")
        self.setMinimumSize(1200, 850)
        self._worker: Optional[AdFetchWorker] = None
        self._ads: List[RawAdRecord] = []
        self._offer_matrix: Optional[OfferMatrixSummary] = None
        self._hook_report: Optional[HookAnalysisReport] = None
        self._brief: Optional[TacticalCreativeBrief] = None
        
        # Ensure database tables exist
        init_db()

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

        self._setup_status_bar()
        self._refresh_watchlist_table()
        self._setup_tray()

    def _make_tray_icon(self) -> QIcon:
        pixmap = QPixmap(48, 48)
        pixmap.fill(QColor("#e63946"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Helvetica", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AL")
        painter.end()
        return QIcon(pixmap)

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(self._make_tray_icon(), parent=self)
        self._tray.setToolTip("AdLens PK — Ad Intelligence Engine")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #e63946;
            }
        """)

        open_action = menu.addAction("Open AdLens PK")
        open_action.triggered.connect(self._tray_open)

        run_action = menu.addAction("Run Scrape Now")
        run_action.triggered.connect(self._tray_run_scrape)

        menu.addSeparator()

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _tray_open(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_run_scrape(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._on_generate_clicked()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_open()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "AdLens PK",
            "AdLens PK is running in the background. Scheduler active.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _setup_status_bar(self) -> None:
        self.statusBarWidget = QStatusBar()
        self.statusBarWidget.setStyleSheet("background-color: #1a1d27; color: #9ca3af; border-top: 1px solid #2d3148;")
        self.setStatusBar(self.statusBarWidget)

        self.status_time = QLabel()
        self.status_db = QLabel("Total Ads in DB: 0")
        self.status_scheduler = QLabel("Scheduler: Active (6h interval)")

        self.statusBarWidget.addWidget(self.status_db)
        self.statusBarWidget.addWidget(self.status_scheduler)
        self.statusBarWidget.addPermanentWidget(self.status_time)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(60000)
        self._update_status()

    def _update_status(self) -> None:
        now = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm")
        self.status_time.setText(f"Current Time: {now}")

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
            QLineEdit {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #e63946;
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
            "Watchlist",
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

    def _build_offer_matrix_page(self) -> QWidget:
        """Constructs Page 1: Offer Matrix."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_label = QLabel("Offer Matrix")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Commercial terms, pricing strategies, cash-on-delivery adoption, and primary calls-to-action.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(18)
        card_cta, self.val_cta = self._create_metric_card("Most Common CTA", "-", "Dominant call to action")
        card_free, self.val_free_delivery = self._create_metric_card("Free Delivery", "-", "Prevalence of free shipping")
        card_cod, self.val_offer_cod = self._create_metric_card("COD Adoption Rate", "-", "Cash on delivery availability")
        card_price, self.val_price_ranges = self._create_metric_card("Price Ranges", "-", "Detected price brackets")
        cards_layout.addWidget(card_cta)
        cards_layout.addWidget(card_free)
        cards_layout.addWidget(card_cod)
        cards_layout.addWidget(card_price)
        layout.addLayout(cards_layout)

        self.offer_table = QTableWidget(0, 4)
        self.offer_table.setHorizontalHeaderLabels(["Page Name", "Price Mentioned", "Has COD", "Primary CTA"])
        self.offer_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.offer_table.verticalHeader().setVisible(False)
        self.offer_table.setMinimumHeight(350)
        layout.addWidget(self.offer_table, 1)

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

        self.export_button = QPushButton("Export Full Report (PDF)")
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
        self.export_button.clicked.connect(self._on_export_pdf_clicked)
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

    def _build_watchlist_page(self) -> QWidget:
        """Constructs Page 5: Competitor Watchlist."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        header_label = QLabel("Competitor Watchlist")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Track specific competitor Facebook brand pages and monitor their advertising activity in real-time.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        # Active monitoring counter label at the top
        self.watchlist_active_label = QLabel("Active monitoring: 0 pages")
        self.watchlist_active_label.setStyleSheet("color: #10b981; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.watchlist_active_label)

        # Add to watchlist controls card
        input_card = QFrame()
        input_card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border: 1px solid #2d3148;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        input_layout = QHBoxLayout(input_card)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(12)

        self.watchlist_input = QLineEdit()
        self.watchlist_input.setPlaceholderText("Enter competitor Facebook page name (e.g. Khaadi, Daraz, Junaid Jamshed)...")
        input_layout.addWidget(self.watchlist_input, 2)

        self.watchlist_industry_combo = QComboBox()
        self.watchlist_industry_combo.addItems(self.industry_options)
        input_layout.addWidget(self.watchlist_industry_combo, 1)

        add_btn = QPushButton("Add Page")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #d62828;
            }
        """)
        add_btn.clicked.connect(self._on_add_to_watchlist)
        input_layout.addWidget(add_btn)

        layout.addWidget(input_card)

        # Watchlist Table
        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(6)
        self.watchlist_table.setHorizontalHeaderLabels([
            "Page Name",
            "Industry",
            "Added Date",
            "Last Seen",
            "Total Ads Found",
            "Action",
        ])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.watchlist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.watchlist_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.watchlist_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.watchlist_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.watchlist_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.watchlist_table.verticalHeader().setVisible(False)
        self.watchlist_table.setMinimumHeight(400)

        layout.addWidget(self.watchlist_table, 1)
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

    def _build_content_stack(self) -> QStackedWidget:
        stack = QStackedWidget()
        stack.setStyleSheet("background-color: #0f1117;")

        # Page 0: Market Overview
        stack.addWidget(self._build_market_overview_page())

        # Page 1: Offer Matrix
        self.offer_matrix_page = self._build_offer_matrix_page()
        stack.addWidget(self.offer_matrix_page)

        # Page 2: Hook Psychology
        stack.addWidget(self._build_hook_psychology_page())

        # Page 3: Strategy Playbook
        stack.addWidget(self._build_strategy_playbook_page())

        # Page 4: Trend Tracker (Scaffold)
        stack.addWidget(self._build_scaffold_page("Trend Tracker"))

        # Page 5: Watchlist
        self.watchlist_page = self._build_watchlist_page()
        stack.addWidget(self.watchlist_page)

        return stack

    def _switch_page(self, index: int) -> None:
        self.content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 5:
            self._refresh_watchlist_table()

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

        # 2. Update Offer Matrix Page
        self.val_cta.setText(offer_matrix.most_common_cta)
        self.val_free_delivery.setText(f"{offer_matrix.free_shipping_prevalence_pct:.1f}%")
        self.val_offer_cod.setText(f"{offer_matrix.cod_prevalence_pct:.1f}%")
        self.val_price_ranges.setText(", ".join(offer_matrix.price_ranges_detected) if offer_matrix.price_ranges_detected else "None")

        self.offer_table.setRowCount(len(offer_matrix.records))
        for row, rec in enumerate(offer_matrix.records):
            p_cell = QTableWidgetItem(rec.page_name)
            pr_cell = QTableWidgetItem(rec.price_mentioned or "N/A")
            c_cell = QTableWidgetItem("Yes" if rec.has_cash_on_delivery else "No")
            cta_cell = QTableWidgetItem(rec.primary_cta)

            for cell in (p_cell, pr_cell, c_cell, cta_cell):
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.offer_table.setItem(row, 0, p_cell)
            self.offer_table.setItem(row, 1, pr_cell)
            self.offer_table.setItem(row, 2, c_cell)
            self.offer_table.setItem(row, 3, cta_cell)

        # 3. Update Hook Psychology Page
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

        # 4. Update Strategy Playbook Page
        self.val_brief_niche.setText(brief.target_niche)
        self.val_brief_whitespace.setText(brief.market_whitespace)
        self.val_brief_angle.setText(brief.recommended_angle)
        self.val_brief_offer.setText(brief.recommended_offer_structure)

        self.hooks_list_widget.clear()
        for idx, hook_text in enumerate(brief.suggested_hooks, start=1):
            list_item = QListWidgetItem(f"Hook #{idx}: {hook_text}")
            self.hooks_list_widget.addItem(list_item)

        self.export_button.setEnabled(True)

        # 5. Refresh Watchlist Stats
        self._refresh_watchlist_table()

    def _on_export_pdf_clicked(self) -> None:
        if not (self._brief and self._offer_matrix and self._hook_report):
            return

        industry_name = self.industry_combo.currentText().lower().replace(" ", "_")
        default_filename = f"adlens_report_{industry_name}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Full Report (PDF)",
            default_filename,
            "PDF Files (*.pdf);;All Files (*)",
        )

        if not file_path:
            return

        try:
            export_report_pdf(
                offer_matrix=self._offer_matrix,
                hook_report=self._hook_report,
                brief=self._brief,
                output_path=file_path,
            )
            os.startfile(file_path)
        except Exception as exc:
            self.market_overview_status.setText(f"PDF export failed: {exc}")
            self.market_overview_status.setStyleSheet("color: #e63946; font-size: 14px;")

    def _on_add_to_watchlist(self) -> None:
        """Handles adding a page to the competitor watchlist."""
        page_name = self.watchlist_input.text().strip()
        if not page_name:
            return

        industry = self.watchlist_industry_combo.currentText()
        try:
            add_to_watchlist(page_name=page_name, industry=industry)
            self.watchlist_input.clear()
            self._refresh_watchlist_table()
        except Exception as exc:
            print(f"Error adding to watchlist: {exc}")

    def _on_remove_from_watchlist(self, page_name: str) -> None:
        """Handles removing a page from the competitor watchlist."""
        try:
            remove_from_watchlist(page_name)
            self._refresh_watchlist_table()
        except Exception as exc:
            print(f"Error removing from watchlist: {exc}")

    def _refresh_watchlist_table(self) -> None:
        """Refreshes the watchlist table with all active entries from the database."""
        try:
            entries = get_watchlist(active_only=True)
            self.watchlist_active_label.setText(f"Active monitoring: {len(entries)} pages")
            self.watchlist_table.setRowCount(len(entries))

            for row_idx, entry in enumerate(entries):
                p_name = QTableWidgetItem(str(entry.get("page_name", "")))
                ind = QTableWidgetItem(str(entry.get("industry", "")))
                added = QTableWidgetItem(str(entry.get("added_at") or "-"))
                seen = QTableWidgetItem(str(entry.get("last_seen_at") or "Never"))
                ads_count = QTableWidgetItem(str(entry.get("total_ads_found", 0)))

                for it in (p_name, ind, added, seen, ads_count):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.watchlist_table.setItem(row_idx, 0, p_name)
                self.watchlist_table.setItem(row_idx, 1, ind)
                self.watchlist_table.setItem(row_idx, 2, added)
                self.watchlist_table.setItem(row_idx, 3, seen)
                self.watchlist_table.setItem(row_idx, 4, ads_count)

                remove_btn = QPushButton("Remove")
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dc2626;
                        color: #ffffff;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #b91c1c;
                    }
                """)
                remove_btn.clicked.connect(
                    lambda checked, name=entry["page_name"]: self._on_remove_from_watchlist(name)
                )
                self.watchlist_table.setCellWidget(row_idx, 5, remove_btn)

        except Exception as exc:
            print(f"Error refreshing watchlist table: {exc}")

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
