import json
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
    QProgressBar,
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
import pyqtgraph as pg

from src.core.schemas import (
    RawAdRecord,
    OfferMatrixSummary,
    HookAnalysisReport,
    TacticalCreativeBrief,
)
from src.core.fetcher import fetch_ads
from src.core.extractor import build_offer_matrix, compute_competitive_density, get_survivor_ads
from src.core.classifier import analyze_hooks, compute_hook_saturation
from src.core.ai_engine import generate_tactical_brief
from src.core.exporter import export_report_pdf
from src.db.watchlist import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    update_watchlist_stats,
)
from src.db.reports import (
    save_report,
    get_report_history,
    get_report_by_id,
)
from src.db.repository import init_db, get_all_ads, get_trend_data, get_new_entrants, get_season_breakdown
from src.desktop.pages.grader_page import GraderPage
from src.desktop.pages.formula_page import WinningFormulaPage
from src.desktop.pages.price_page import PriceIntelligencePage
from src.desktop.pages.ml_training_page import MLTrainingPage
from src.desktop.pages.whatsapp_page import WhatsAppAnalyzerPage
from src.desktop.pages.velocity_page import TrendVelocityPage
from src.ml.scheduler_hook import schedule_weekly_retrain


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


class CollectionWorker(QThread):
    """Background worker that runs ad collection for multiple industries sequentially."""
    progress = pyqtSignal(int, str, int, int)  # industry_index, industry_name, ads_found, ads_saved
    status_update = pyqtSignal(str)
    collection_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, industries: List[str]) -> None:
        super().__init__()
        self.industries = industries
        self._is_cancelled = False

    def run(self) -> None:
        import time
        from datetime import datetime
        try:
            from src.core.scraper import scrape_ads_sync
            from src.db.repository import save_ads

            for idx, industry in enumerate(self.industries):
                if self._is_cancelled:
                    self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Collection cancelled by user.")
                    break

                self.status_update.emit(f"Collecting {industry}...")
                self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] {industry.upper()}: Starting collection...")
                try:
                    ads = scrape_ads_sync(industry, max_ads=50)
                    count = save_ads(ads)
                    self.progress.emit(idx, industry, len(ads), count)
                    self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] {industry.upper()}: Found {len(ads)} ads, saved {count} new")
                except Exception as exc:
                    self.error_occurred.emit(f"{industry}: {exc}")
                    self.progress.emit(idx, industry, 0, 0)
                    self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] {industry.upper()}: Error - {exc}")

            self.status_update.emit("Collection complete")
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] SYSTEM ERROR: {exc}")
        finally:
            self.collection_finished.emit()

    def cancel(self) -> None:
        self._is_cancelled = True


class AdLensPKWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AdLens PK — Pakistani Ad Intelligence")
        self.setMinimumSize(1200, 850)
        self._worker: Optional[AdFetchWorker] = None
        self._collection_worker: Optional[CollectionWorker] = None
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
        self._apply_table_styles()
        main_layout.addWidget(self.content_stack, 1)

        self._setup_status_bar()
        self._refresh_watchlist_table()
        self._refresh_history_table()
        self._setup_tray()

        # Switch to Home dashboard on startup and populate from DB
        self._switch_page(0)
        self._refresh_home()

        # Auto-refresh home dashboard every 5 minutes
        self._home_refresh_timer = QTimer(self)
        self._home_refresh_timer.timeout.connect(self._refresh_home)
        self._home_refresh_timer.start(300000)

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

    def _make_sidebar_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            "color: #6b7280; font-size: 10px; font-weight: 600; text-transform: uppercase; "
            "letter-spacing: 1.5px; margin-top: 8px; margin-bottom: 4px; background-color: transparent; border: none;"
        )
        return label

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color: #1a1d27; border-right: 1px solid #2d3148;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar:vertical { width: 4px; background: #1a1d27; } QScrollBar::handle:vertical { background: #2d3148; border-radius: 2px; }")

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background-color: #1a1d27;")
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(4)
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
                background-color: #f04855;
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

        self.nav_buttons: list[QPushButton] = []
        self.page_names = [
            "Home",
            "Live Collection",
            "Winning Formula",
            "Market Overview",
            "Offer Matrix",
            "Hook Psychology",
            "Strategy Playbook",
            "Price Intel",
            "WhatsApp Intel",
            "Trend Tracker",
            "Trend Velocity",
            "Ad Grader",
            "Brand Profile",
            "ML Training",
            "Watchlist",
            "Report History",
        ]

        nav_sections = [
            ("Overview", ["Home", "Live Collection"]),
            ("Intelligence", ["Winning Formula", "Market Overview", "Offer Matrix", "Hook Psychology", "Strategy Playbook"]),
            ("Research", ["Price Intel", "WhatsApp Intel", "Trend Tracker", "Trend Velocity"]),
            ("Tools", ["Ad Grader", "Brand Profile", "ML Training"]),
            ("History", ["Watchlist", "Report History"]),
        ]

        section_index = 0
        for section_name, section_pages in nav_sections:
            layout.addWidget(self._make_sidebar_header(section_name))
            for page_name in section_pages:
                btn = QPushButton(page_name)
                btn.setCheckable(True)
                btn.setAutoExclusive(True)
                btn.setStyleSheet("""
                    QPushButton {
                        color: #cccccc;
                        background-color: transparent;
                        border: none;
                        padding: 7px 8px 7px 12px;
                        text-align: left;
                        font-size: 12px;
                        font-family: Segoe UI;
                    }
                    QPushButton:hover { background-color: #2d3148; color: #ffffff; }
                    QPushButton:checked { background-color: #1e2130; color: #ffffff; border-left: 3px solid #e63946; }
                """)
                btn.clicked.connect(lambda checked, i=section_index: self._switch_page(i))
                self.nav_buttons.append(btn)
                layout.addWidget(btn)
                section_index += 1

        self.nav_buttons[0].setChecked(True)
        layout.addStretch()

        version_label = QLabel("v1.0 — Beta")
        version_label.setStyleSheet("color: #4b5563; font-size: 10px; background: none; border: none;")
        layout.addWidget(version_label)

        scroll.setWidget(inner_widget)
        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        return sidebar


    @staticmethod
    def _card_style(padding: int = 16) -> str:
        return f"""
            QFrame {{
                background-color: #1e2130;
                border-radius: 10px;
                border-left: 3px solid #e63946;
                border-top: 1px solid #2d3148;
                border-right: 1px solid #2d3148;
                border-bottom: 1px solid #2d3148;
                padding: {padding}px;
            }}
        """

    @staticmethod
    def _create_section_header(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        return label

    @staticmethod
    def _style_table(table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            "QTableWidget { gridline-color: #2d3148; alternate-background-color: #1a1d27; } "
            "QHeaderView::section { background-color: #1e2130; color: #9ca3af; "
            "font-size: 11px; font-weight: 600; padding: 6px; border: none; }"
        )
        table.horizontalHeader().setStretchLastSection(True)

    def _apply_table_styles(self) -> None:
        for table in self.findChildren(QTableWidget):
            self._style_table(table)
            if table.property("fixed_last_column"):
                table.horizontalHeader().setStretchLastSection(False)

    @staticmethod
    def _create_scrollable_page(
        spacing: int = 20, margins: Tuple[int, int, int, int] = (32, 32, 32, 32)
    ) -> Tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0f1117; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(spacing)
        content_layout.setContentsMargins(*margins)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(content_widget)
        page_layout.addWidget(scroll)
        return page, content_layout

    def _clear_home_formula_cards(self) -> None:
        while self.home_formula_layout.count():
            item = self.home_formula_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

    def _add_home_formula_card(self, text: str) -> None:
        card = QFrame()
        card.setStyleSheet(self._card_style(padding=12))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(0)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #ffffff; font-size: 13px; background: transparent; border: none;")
        card_layout.addWidget(label)
        self.home_formula_layout.addWidget(card)

    def _create_metric_card(self, label: str, value: str, subtitle: str = "") -> tuple:
        card = QFrame()
        card.setMinimumHeight(90)
        card.setStyleSheet(self._card_style(padding=0))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        label_widget = QLabel(label.upper())
        label_widget.setFixedHeight(14)
        label_widget.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600; background: transparent; border: none;")

        value_widget = QLabel(str(value))
        value_widget.setFixedHeight(28)
        value_widget.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 700; background: transparent; border: none;")

        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setFixedHeight(12)
            sub.setStyleSheet("color: #6b7280; font-size: 10px; background: transparent; border: none;")
            layout.addWidget(sub)

        layout.addStretch()
        return card, value_widget

    def _build_home_page(self) -> QWidget:
        """Builds the auto-loading home dashboard showing live market metrics from the database."""
        page, layout = self._create_scrollable_page(
            spacing=20, margins=(32, 24, 32, 32)
        )

        header_label = QLabel("Pakistani Ad Intelligence — Live Market View")
        header_font = QFont()
        header_font.setPointSize(22)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        self.home_subtitle = QLabel("Last updated: —")
        self.home_subtitle.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(self.home_subtitle)

        layout.addWidget(self._create_section_header("Market Overview"))
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)

        card_total, self.home_val_total = self._create_metric_card("Total Ads Tracked", "-", "All ads in database")
        card_industries, self.home_val_industries = self._create_metric_card("Industries Covered", "-", "Unique industry count")
        card_avg_days, self.home_val_avg_days = self._create_metric_card("Avg Days Active", "-", "Mean ad longevity")
        card_cod, self.home_val_cod = self._create_metric_card("COD Adoption Rate", "-", "Cash on delivery prevalence")

        for card in (card_total, card_industries, card_avg_days, card_cod):
            card.setFixedHeight(100)
            card.setMinimumWidth(200)
            cards_layout.addWidget(card, 1)
        layout.addLayout(cards_layout)

        layout.addWidget(self._create_section_header("Key Insights"))
        self.home_insight_card = QFrame()
        self.home_insight_card.setMinimumHeight(80)
        self.home_insight_card.setStyleSheet(self._card_style())
        insight_layout = QVBoxLayout(self.home_insight_card)
        insight_layout.setContentsMargins(16, 12, 16, 12)
        insight_layout.setSpacing(6)

        insight_title = QLabel("Top Insight")
        insight_title.setStyleSheet("color: #e63946; font-size: 12px; font-weight: 700; text-transform: uppercase; border: none; background: transparent;")
        self.home_insight_text = QLabel("Analyzing database...")
        self.home_insight_text.setWordWrap(True)
        self.home_insight_text.setMinimumHeight(60)
        self.home_insight_text.setStyleSheet("color: #ffffff; font-size: 13px; padding: 8px; border: none; background: transparent;")

        insight_layout.addWidget(insight_title)
        insight_layout.addWidget(self.home_insight_text)
        layout.addWidget(self.home_insight_card)

        layout.addWidget(self._create_section_header("Market at a Glance"))
        glance_cards_layout = QHBoxLayout()
        glance_cards_layout.setSpacing(20)

        card_active_adv, self.home_val_active_adv = self._create_metric_card("Most Active Advertiser", "-", "Brand with most ads")
        card_adv_ind, self.home_val_adv_ind = self._create_metric_card("Most Advertised Industry", "-", "Industry with most ads")
        card_avg_lifespan, self.home_val_avg_lifespan = self._create_metric_card("Average Ad Lifespan", "-", "Overall average days")

        for card in (card_active_adv, card_adv_ind, card_avg_lifespan):
            card.setMinimumHeight(90)
            glance_cards_layout.addWidget(card, 1)
        layout.addLayout(glance_cards_layout)

        layout.addWidget(self._create_section_header("Industry Distribution"))
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(20)

        industry_chart_layout = QVBoxLayout()
        industry_chart_layout.setSpacing(8)
        industry_chart_layout.addWidget(self._create_section_header("Ads by Industry"))
        self.home_industry_chart = pg.PlotWidget()
        self.home_industry_chart.setBackground("#1e2130")
        self.home_industry_chart.getAxis('bottom').setPen('#9ca3af')
        self.home_industry_chart.getAxis('left').setPen('#9ca3af')
        self.home_industry_chart.getAxis('bottom').setTextPen('#ffffff')
        self.home_industry_chart.getAxis('left').setTextPen('#ffffff')
        self.home_industry_chart.setFixedHeight(200)
        industry_chart_layout.addWidget(self.home_industry_chart)
        charts_layout.addLayout(industry_chart_layout, 1)

        cod_chart_layout = QVBoxLayout()
        cod_chart_layout.setSpacing(8)
        cod_chart_layout.addWidget(self._create_section_header("COD Adoption Rate (%)"))
        self.home_cod_chart = pg.PlotWidget()
        self.home_cod_chart.setBackground("#1e2130")
        self.home_cod_chart.getAxis('bottom').setPen('#9ca3af')
        self.home_cod_chart.getAxis('left').setPen('#9ca3af')
        self.home_cod_chart.getAxis('bottom').setTextPen('#ffffff')
        self.home_cod_chart.getAxis('left').setTextPen('#ffffff')
        self.home_cod_chart.setFixedHeight(200)
        cod_chart_layout.addWidget(self.home_cod_chart)
        charts_layout.addLayout(cod_chart_layout, 1)
        layout.addLayout(charts_layout)

        layout.addWidget(self._create_section_header("Top Performing Ads"))
        self.home_top_ads_table = QTableWidget(0, 5)
        self.home_top_ads_table.setHorizontalHeaderLabels(["Brand", "Industry", "Days Active", "CTA", "Has COD"])
        self.home_top_ads_table.setProperty("fixed_last_column", True)
        self._style_table(self.home_top_ads_table)
        home_header = self.home_top_ads_table.horizontalHeader()
        home_header.setStretchLastSection(False)
        home_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 100), (2, 90), (3, 140), (4, 70)):
            home_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.home_top_ads_table.setColumnWidth(column, width)
        self.home_top_ads_table.verticalHeader().setVisible(False)
        self.home_top_ads_table.setMinimumHeight(220)
        layout.addWidget(self.home_top_ads_table)

        layout.addWidget(self._create_section_header("Winning Formula by Industry"))
        self.home_formula_container = QWidget()
        self.home_formula_container.setStyleSheet("background: transparent;")
        self.home_formula_layout = QVBoxLayout(self.home_formula_container)
        self.home_formula_layout.setContentsMargins(0, 0, 0, 0)
        self.home_formula_layout.setSpacing(8)
        layout.addWidget(self.home_formula_container)

        self.home_bottom_updated = QLabel("Database last updated: — | 0 ads tracked")
        self.home_bottom_updated.setStyleSheet("color: #9ca3af; font-size: 12px; margin-top: 12px;")
        self.home_bottom_updated.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.home_bottom_updated)
        layout.addStretch()
        return page

    def _build_collection_page(self) -> QWidget:
        from PyQt6.QtWidgets import QTextEdit
        page, layout = self._create_scrollable_page(spacing=24)

        # Header
        header_label = QLabel("Live Data Collection")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Watch AdLens PK scrape real Pakistani ads in real-time")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        # Status Banner
        banner_frame = QFrame()
        banner_frame.setStyleSheet(self._card_style())
        banner_layout = QHBoxLayout(banner_frame)
        banner_layout.setSpacing(32)

        self.coll_last_run_lbl = QLabel("Last Run: Never")
        self.coll_last_run_lbl.setStyleSheet("color: #ffffff; font-size: 14px; border: none;")
        self.coll_collected_lbl = QLabel("Ads Collected Last Run: 0")
        self.coll_collected_lbl.setStyleSheet("color: #ffffff; font-size: 14px; border: none;")
        self.coll_total_db_lbl = QLabel("Current DB Total: 0")
        self.coll_total_db_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600; border: none;")

        banner_layout.addWidget(self.coll_last_run_lbl)
        banner_layout.addWidget(self.coll_collected_lbl)
        banner_layout.addWidget(self.coll_total_db_lbl)
        banner_layout.addStretch()
        layout.addWidget(banner_frame)

        # Industry Selector Grid
        ind_title = self._create_section_header("Select Industries to Collect")
        layout.addWidget(ind_title)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(12)
        self.industry_toggles = []

        # We take first 8 industries for the grid
        industries = self.industry_options[:8] if hasattr(self, 'industry_options') else []
        for ind in industries:
            btn = QPushButton(ind)
            btn.setCheckable(True)
            btn.setChecked(True) # Default all selected
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e2130;
                    color: #9ca3af;
                    border: 1px solid #2d3148;
                    border-radius: 6px;
                    padding: 12px;
                    font-weight: 600;
                }
                QPushButton:checked {
                    background-color: #3b1418;
                    color: #ffffff;
                    border: 1px solid #e63946;
                    box-shadow: 0 0 8px #e63946;
                }
            """)
            self.industry_toggles.append(btn)
            grid_layout.addWidget(btn)

        layout.addLayout(grid_layout)

        # Run controls row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(16)

        self.start_coll_btn = QPushButton("Start Collection")
        self.start_coll_btn.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 14px 28px;
                font-weight: 700;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #f04855; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """)
        self.start_coll_btn.clicked.connect(self._on_start_collection)
        controls_layout.addWidget(self.start_coll_btn)

        self.stop_coll_btn = QPushButton("Stop")
        self.stop_coll_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 14px 28px;
                font-weight: 600;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #2d3148; }
            QPushButton:disabled { background-color: #1a1d27; color: #4b5563; }
        """)
        self.stop_coll_btn.setEnabled(False)
        self.stop_coll_btn.clicked.connect(self._on_stop_collection)
        controls_layout.addWidget(self.stop_coll_btn)

        est_time_lbl = QLabel("Est. 15-20 minutes for all industries")
        est_time_lbl.setStyleSheet("color: #9ca3af; font-size: 13px;")
        controls_layout.addWidget(est_time_lbl)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # Real-time log
        log_title = self._create_section_header("Live Collection Log")
        layout.addWidget(log_title)

        self.coll_log_edit = QTextEdit()
        self.coll_log_edit.setReadOnly(True)
        self.coll_log_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0c0d12;
                color: #a9b1d6;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #2d3148;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.coll_log_edit, 1)

        # Progress section
        self.coll_progress_bar = QProgressBar()
        self.coll_progress_bar.setMinimum(0)
        self.coll_progress_bar.setMaximum(100)
        self.coll_progress_bar.setValue(0)
        self.coll_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e2130;
                border: 1px solid #2d3148;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #e63946;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.coll_progress_bar)

        self.coll_status_table = QTableWidget(0, 4)
        self.coll_status_table.setHorizontalHeaderLabels(["Industry", "Status", "Ads Found", "Saved New"])
        self.coll_status_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.coll_status_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.coll_status_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.coll_status_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.coll_status_table.verticalHeader().setVisible(False)
        self.coll_status_table.setMinimumHeight(200)
        layout.addWidget(self.coll_status_table)

        return page

    def _build_market_overview_page(self) -> QWidget:
        """Constructs the Market Overview page featuring three metric cards as QFrame widgets."""
        page, layout = self._create_scrollable_page(spacing=24)

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
        # Survivor Ads Section
        survivor_title = self._create_section_header("Survivor Ads")
        layout.addWidget(survivor_title)

        survivor_sub = QLabel("Long-running ads (30+ days) — proven creative winners worth emulating.")
        survivor_sub.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(survivor_sub)

        survivor_cards_layout = QHBoxLayout()
        survivor_cards_layout.setSpacing(18)
        card_survivor_count, self.val_survivor_count = self._create_metric_card(
            "Survivor Ads", "-", "Ads running 30+ days"
        )
        card_survivor_pct, self.val_survivor_pct = self._create_metric_card(
            "Survivor Share", "-", "Percentage of total evaluated ads"
        )
        survivor_cards_layout.addWidget(card_survivor_count)
        survivor_cards_layout.addWidget(card_survivor_pct)
        survivor_cards_layout.addStretch()
        layout.addLayout(survivor_cards_layout)

        self.survivor_table = QTableWidget(0, 4)
        self.survivor_table.setHorizontalHeaderLabels([
            "Page Name", "Days Active", "Primary CTA", "Has COD"
        ])
        self.survivor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.survivor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.survivor_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.survivor_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.survivor_table.verticalHeader().setVisible(False)
        self.survivor_table.setMinimumHeight(220)
        layout.addWidget(self.survivor_table, 1)

        layout.addStretch()
        return page

    def _build_offer_matrix_page(self) -> QWidget:
        """Constructs Page 1: Offer Matrix."""
        page, layout = self._create_scrollable_page()

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
        self.offer_table.setMinimumHeight(280)
        layout.addWidget(self.offer_table, 1)

        # Market Structure section
        ms_title = self._create_section_header("Market Structure")
        layout.addWidget(ms_title)

        ms_cards_layout = QHBoxLayout()
        ms_cards_layout.setSpacing(18)
        card_ua, self.val_unique_advertisers = self._create_metric_card(
            "Unique Advertisers", "-", "Distinct brands running ads"
        )
        card_apb, self.val_avg_ads_per_brand = self._create_metric_card(
            "Avg Ads / Brand", "-", "Average ad volume per advertiser"
        )
        card_db, self.val_dominant_brand = self._create_metric_card(
            "Dominant Brand", "-", "Brand with highest ad volume"
        )
        card_tbc, self.val_top_brand_count = self._create_metric_card(
            "Top Brand Ad Count", "-", "Ads from the dominant brand"
        )
        ms_cards_layout.addWidget(card_ua)
        ms_cards_layout.addWidget(card_apb)
        ms_cards_layout.addWidget(card_db)
        ms_cards_layout.addWidget(card_tbc)
        layout.addLayout(ms_cards_layout)

        top5_label = QLabel("Top 5 Brands by Ad Volume")
        top5_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 600; margin-top: 4px;")
        layout.addWidget(top5_label)

        self.top5_brands_table = QTableWidget(0, 2)
        self.top5_brands_table.setHorizontalHeaderLabels(["Brand (Page Name)", "Ad Count"])
        self.top5_brands_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.top5_brands_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.top5_brands_table.verticalHeader().setVisible(False)
        self.top5_brands_table.setFixedHeight(180)
        layout.addWidget(self.top5_brands_table)

        return page

    def _build_hook_psychology_page(self) -> QWidget:
        """Constructs Page 2: Hook Psychology with Dominant Angle metric card and detailed hooks table."""
        page, layout = self._create_scrollable_page()

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
        table_title = self._create_section_header("Extracted Ad Hooks & Classifications")
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
        self.hooks_table.setMinimumHeight(220)

        layout.addWidget(self.hooks_table, 1)

        # Hook Saturation Index table
        sat_title = self._create_section_header("Hook Saturation Index")
        layout.addWidget(sat_title)

        sat_sub = QLabel("Market share and saturation level for each hook archetype.")
        sat_sub.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(sat_sub)

        self.saturation_table = QTableWidget(0, 4)
        self.saturation_table.setHorizontalHeaderLabels([
            "Hook Type", "Count", "Market Share %", "Status"
        ])
        self.saturation_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.saturation_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.saturation_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.saturation_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.saturation_table.verticalHeader().setVisible(False)
        self.saturation_table.setFixedHeight(200)
        layout.addWidget(self.saturation_table)

        return page

    def _build_strategy_playbook_page(self) -> QWidget:
        """Constructs Page 3: Strategy Playbook with Gemini AI brief card, copy hooks list, and export button."""
        page, layout = self._create_scrollable_page()

        # Header row with Export Buttons
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

        self.export_pdf_button = QPushButton("Export PDF Report")
        self.export_pdf_button.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #d62828;
            }
            QPushButton:disabled {
                background-color: #1a1d27;
                color: #4b5563;
                border: 1px solid #2d3148;
            }
        """)
        self.export_pdf_button.setEnabled(False)
        self.export_pdf_button.clicked.connect(self._on_export_pdf_clicked)
        header_row.addWidget(self.export_pdf_button)

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

        brief_content_layout = QVBoxLayout()
        brief_content_layout.setContentsMargins(0, 0, 0, 0)
        brief_content_layout.setSpacing(18)

        # 1. Dark QFrame Card for Gemini AI Brief
        brief_card = QFrame()
        brief_card.setStyleSheet(self._card_style())
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

        brief_content_layout.addWidget(brief_card)

        # 2. Suggested Copy Hooks Section
        hooks_title = self._create_section_header("Suggested Copy Hooks")
        brief_content_layout.addWidget(hooks_title)

        self.hooks_list_widget = QListWidget()
        self.hooks_list_widget.setMinimumHeight(180)
        brief_content_layout.addWidget(self.hooks_list_widget)

        layout.addLayout(brief_content_layout)

        return page

    def _build_watchlist_page(self) -> QWidget:
        """Constructs Page 5: Competitor Watchlist."""
        page, layout = self._create_scrollable_page()

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
        input_card.setStyleSheet(self._card_style(padding=12))
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

    def _build_report_history_page(self) -> QWidget:
        """Constructs Page 6: Report History."""
        page, layout = self._create_scrollable_page()

        # Header
        header_label = QLabel("Report History")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Historical audit archive of generated market reports, offer structures, and tactical strategy briefs.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        # Counter label
        self.history_count_label = QLabel("Saved reports: 0")
        self.history_count_label.setStyleSheet("color: #3b82f6; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.history_count_label)

        # History Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Date",
            "Industry",
            "Total Ads",
            "COD Rate",
            "Dominant Hook",
            "Recommended Angle",
            "Action",
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setMinimumHeight(450)

        layout.addWidget(self.history_table, 1)
        return page


    def _build_brand_profile_page(self) -> QWidget:
        """Constructs Page 7: Brand Profile with search and metrics."""
        page, layout = self._create_scrollable_page()

        header_label = QLabel("Brand Profile")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Search for any brand to view their advertising profile and track activity.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        # Search row
        search_row = QHBoxLayout()
        self.brand_search_input = QLineEdit()
        self.brand_search_input.setPlaceholderText("Enter brand name and press Enter (e.g. Khaadi, Daraz, Junaid Jamshed)...")
        self.brand_search_input.returnPressed.connect(self._on_brand_search)
        search_row.addWidget(self.brand_search_input, 1)

        self.track_brand_button = QPushButton("Track This Brand")
        self.track_brand_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.track_brand_button.setEnabled(False)
        self.track_brand_button.clicked.connect(self._on_track_brand_clicked)
        search_row.addWidget(self.track_brand_button)
        layout.addLayout(search_row)

        # Metrics card row
        metrics_card = QFrame()
        metrics_card.setStyleSheet(self._card_style())
        metrics_layout = QHBoxLayout(metrics_card)
        metrics_layout.setSpacing(24)

        def _metric_block(title: str) -> Tuple[QVBoxLayout, QLabel]:
            block = QVBoxLayout()
            t = QLabel(title)
            t.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 600; border: none; background: transparent;")
            v = QLabel("-")
            v_font = QFont()
            v_font.setPointSize(18)
            v_font.setBold(True)
            v.setFont(v_font)
            v.setStyleSheet("color: #ffffff; border: none; background: transparent;")
            block.addWidget(t)
            block.addWidget(v)
            return block, v

        block_total, self.bp_val_total = _metric_block("Total Ads")
        block_avg, self.bp_val_avg_days = _metric_block("Avg Days Active")
        block_cta, self.bp_val_cta = _metric_block("Most Used CTA")
        block_cod, self.bp_val_cod = _metric_block("COD Usage")

        for block, _ in [(block_total, self.bp_val_total), (block_avg, self.bp_val_avg_days), (block_cta, self.bp_val_cta), (block_cod, self.bp_val_cod)]:
            metrics_layout.addLayout(block)

        layout.addWidget(metrics_card)

        # Ads table
        ads_section_label = self._create_section_header("Ad Records")
        layout.addWidget(ads_section_label)

        self.brand_ads_table = QTableWidget(0, 5)
        self.brand_ads_table.setHorizontalHeaderLabels([
            "Date Pulled", "Ad Copy (100 chars)", "Days Active", "Has COD", "Primary CTA"
        ])
        self.brand_ads_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.brand_ads_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.brand_ads_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.brand_ads_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.brand_ads_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.brand_ads_table.verticalHeader().setVisible(False)
        self.brand_ads_table.setMinimumHeight(350)
        layout.addWidget(self.brand_ads_table, 1)

        return page




    def _build_trend_tracker_page(self) -> QWidget:
        """Constructs Page 4: Trend Tracker with new entrants and season breakdown."""
        page, layout = self._create_scrollable_page()

        header_label = QLabel("Trend Tracker")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel("Monitor emerging brands, weekly new entrants, and ad seasonality in the Pakistani market.")
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub_label)

        # New This Week section
        section_label = self._create_section_header("New This Week")
        layout.addWidget(section_label)

        section_sub = QLabel("Brands that first appeared in the last 7 days with 1-2 ads detected.")
        section_sub.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(section_sub)

        self.new_entrants_count_label = QLabel("New entrants found: 0")
        self.new_entrants_count_label.setStyleSheet("color: #f59e0b; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.new_entrants_count_label)

        self.new_entrants_table = QTableWidget(0, 4)
        self.new_entrants_table.setHorizontalHeaderLabels([
            "Brand Name", "Industry", "First Seen", "Ads Found"
        ])
        self.new_entrants_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.new_entrants_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.new_entrants_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.new_entrants_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.new_entrants_table.verticalHeader().setVisible(False)
        self.new_entrants_table.setMinimumHeight(220)
        layout.addWidget(self.new_entrants_table)

        # Season Breakdown Section
        season_title = self._create_section_header("Seasonality Breakdown")
        layout.addWidget(season_title)

        season_sub = QLabel("Ad counts grouped by Pakistani e-commerce season tag.")
        season_sub.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(season_sub)

        self.season_table = QTableWidget(0, 2)
        self.season_table.setHorizontalHeaderLabels(["Season Tag", "Ad Count"])
        self.season_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.season_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.season_table.verticalHeader().setVisible(False)
        self.season_table.setMinimumHeight(220)
        layout.addWidget(self.season_table, 1)

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

        # Page 0: Home Dashboard
        self.home_page = self._build_home_page()
        stack.addWidget(self.home_page)

        # Page 1: Live Collection
        self.collection_page = self._build_collection_page()
        stack.addWidget(self.collection_page)

        # Page 2: Winning Formula
        self.formula_page = WinningFormulaPage()
        stack.addWidget(self.formula_page)

        # Page 3: Market Overview
        stack.addWidget(self._build_market_overview_page())

        # Page 4: Offer Matrix
        self.offer_matrix_page = self._build_offer_matrix_page()
        stack.addWidget(self.offer_matrix_page)

        # Page 5: Hook Psychology
        stack.addWidget(self._build_hook_psychology_page())

        # Page 6: Strategy Playbook
        stack.addWidget(self._build_strategy_playbook_page())

        # Page 7: Price Intel
        self.price_intel_page = PriceIntelligencePage()
        stack.addWidget(self.price_intel_page)

        # Page 8: WhatsApp Intel
        self.whatsapp_intel_page = WhatsAppAnalyzerPage()
        stack.addWidget(self.whatsapp_intel_page)

        # Page 9: Trend Tracker
        self.trend_tracker_page = self._build_trend_tracker_page()
        stack.addWidget(self.trend_tracker_page)

        # Page 10: Trend Velocity
        self.trend_velocity_page = TrendVelocityPage()
        stack.addWidget(self.trend_velocity_page)

        # Page 11: Ad Grader
        self.ad_grader_page = GraderPage()
        stack.addWidget(self.ad_grader_page)

        # Page 12: Brand Profile
        self.brand_profile_page = self._build_brand_profile_page()
        stack.addWidget(self.brand_profile_page)

        # Page 13: ML Training
        self.ml_training_page = MLTrainingPage()
        stack.addWidget(self.ml_training_page)

        # Page 14: Watchlist
        self.watchlist_page = self._build_watchlist_page()
        stack.addWidget(self.watchlist_page)

        # Page 15: Report History
        self.history_page = self._build_report_history_page()
        stack.addWidget(self.history_page)

        return stack

    def _switch_page(self, index: int) -> None:
        self.content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 0:
            self._refresh_home()
        elif index == 1:
            self._refresh_collection_stats()
        elif index == 9:
            self._refresh_new_entrants_table()
            self._refresh_season_breakdown()
        elif index == 14:
            self._refresh_watchlist_table()
        elif index == 15:
            self._refresh_history_table()

    def _refresh_home(self) -> None:
        """Populates the home dashboard from the database without any button click."""
        try:
            all_ads = get_all_ads()
            total = len(all_ads)
            self.home_val_total.setText(f"{total:,}")

            if total == 0:
                self.home_subtitle.setText("Last updated: —")
                self.home_val_industries.setText("0")
                self.home_val_avg_days.setText("-")
                self.home_val_cod.setText("-")
                self.home_insight_text.setText("No ad data in database yet. Run a scrape to populate insights.")
                self.home_top_ads_table.setRowCount(0)
                self._clear_home_formula_cards()
                return

            from datetime import datetime as _dt

            pulled_dates = []
            industries = set()
            days_list = []
            cod_count = 0
            industry_cod_days: Dict[str, list] = {}
            industry_noncod_days: Dict[str, list] = {}
            industry_winners: Dict[str, list] = {}

            now = _dt.utcnow()
            for ad in all_ads:
                ind = str(ad.get("industry") or "General")
                industries.add(ind)

                has_cod = bool(ad.get("has_cod"))
                if has_cod:
                    cod_count += 1

                pulled_raw = ad.get("pulled_at")
                if pulled_raw:
                    try:
                        pulled_dt = _dt.fromisoformat(pulled_raw)
                        days_active = max(0, (now - pulled_dt).days)
                        days_list.append(days_active)
                        pulled_dates.append(pulled_raw)

                        if has_cod:
                            industry_cod_days.setdefault(ind, []).append(days_active)
                        else:
                            industry_noncod_days.setdefault(ind, []).append(days_active)

                        if days_active >= 30:
                            industry_winners.setdefault(ind, []).append(ad)
                    except (ValueError, TypeError):
                        pass

            most_recent = max(pulled_dates) if pulled_dates else "—"
            self.home_subtitle.setText(f"Last updated: {most_recent[:16]}")
            if hasattr(self, 'home_bottom_updated'):
                self.home_bottom_updated.setText(f"Database last updated: {most_recent[:16]} | {total} ads tracked")

            self.home_val_industries.setText(str(len(industries)))

            avg_days = round(sum(days_list) / len(days_list), 1) if days_list else 0
            self.home_val_avg_days.setText(str(avg_days))

            cod_pct = round(cod_count / total * 100, 1)
            self.home_val_cod.setText(f"{cod_pct}%")

            NOISE_BRANDS = {'video player', 'video', 'player', 'sponsored', 'see more', 'learn more', 'shop now', 'ad', 'facebook', 'instagram', 'unknown', 'none', 'advertisement'}
            brands = [a['page_name'] for a in all_ads if a.get('page_name') and len(a['page_name']) > 3 and a['page_name'].lower().strip() not in NOISE_BRANDS and not a['page_name'].lower().startswith('http')]
            top_page = Counter(brands).most_common(1)[0][0] if brands else "-"
            self.home_val_active_adv.setText(top_page)

            ind_names = [str(ad.get("industry") or "General") for ad in all_ads]
            top_ind = Counter(ind_names).most_common(1)[0][0] if ind_names else "-"
            self.home_val_adv_ind.setText(top_ind)
            self.home_val_avg_lifespan.setText(str(avg_days))

            industry_avgs = {}
            for ind in industries:
                d_list = industry_cod_days.get(ind, []) + industry_noncod_days.get(ind, [])
                if d_list:
                    industry_avgs[ind] = sum(d_list) / len(d_list)

            try:
                import pandas as pd
                df = pd.DataFrame(all_ads)
                if not df.empty and 'industry' in df.columns:
                    industry_counts = df['industry'].value_counts()
                    top_industry = industry_counts.index[0]
                    top_count = industry_counts.iloc[0]
                    cod_count = df[df['has_cod'] == True].shape[0] if 'has_cod' in df.columns else 0
                    cod_pct = round((cod_count / len(df)) * 100, 1)
                    insight_text = f"AdLens PK is tracking {len(df):,} Pakistani ads across {df['industry'].nunique()} industries. {top_industry} leads with {top_count} ads. Overall COD adoption: {cod_pct}%."
                    self.home_insight_text.setText(insight_text)
            except Exception as e:
                self.home_insight_text.setText(f"{total:,} Pakistani ads tracked across {len(industries)} industries.")

            self.home_industry_chart.clear()
            ind_counts = Counter(ind_names)
            sorted_inds = ind_counts.most_common(8)

            y_pos = list(range(len(sorted_inds)))
            y_pos.reverse()
            counts = [item[1] for item in sorted_inds]
            labels = [item[0] for item in sorted_inds]

            bg_ind = pg.BarGraphItem(x0=0, y=y_pos, width=counts, height=0.6, brush='#e63946')
            self.home_industry_chart.addItem(bg_ind)
            self.home_industry_chart.getAxis('left').setTicks([list(zip(y_pos, labels))])

            for y, x in zip(y_pos, counts):
                text = pg.TextItem(f"{x}", color='#ffffff', anchor=(0, 0.5))
                self.home_industry_chart.addItem(text)
                text.setPos(x + (max(counts) * 0.02), y)

            self.home_cod_chart.clear()
            cod_rates = []
            for ind in sorted_inds:
                name = ind[0]
                c_days = len(industry_cod_days.get(name, []))
                nc_days = len(industry_noncod_days.get(name, []))
                tot_days_cat = c_days + nc_days
                rate = (c_days / tot_days_cat * 100) if tot_days_cat > 0 else 0
                cod_rates.append((name, rate))

            cod_rates = sorted(cod_rates, key=lambda x: x[1])
            y_pos_cod = list(range(len(cod_rates)))
            rates = [item[1] for item in cod_rates]
            labels_cod = [item[0] for item in cod_rates]

            bg_cod = pg.BarGraphItem(x0=0, y=y_pos_cod, width=rates, height=0.6, brush='#d62828')
            self.home_cod_chart.addItem(bg_cod)
            self.home_cod_chart.getAxis('left').setTicks([list(zip(y_pos_cod, labels_cod))])

            for y, x in zip(y_pos_cod, rates):
                text = pg.TextItem(f"{x:.1f}%", color='#ffffff', anchor=(0, 0.5))
                self.home_cod_chart.addItem(text)
                text.setPos(x + 2, y)

            sorted_ads = sorted(
                all_ads,
                key=lambda a: max(0, (now - _dt.fromisoformat(a["pulled_at"])).days)
                if a.get("pulled_at") else 0,
                reverse=True,
            )[:10]

            self.home_top_ads_table.setRowCount(len(sorted_ads))
            for row_idx, ad in enumerate(sorted_ads):
                pulled_raw = ad.get("pulled_at") or ""
                try:
                    days_active = max(0, (now - _dt.fromisoformat(pulled_raw)).days)
                except (ValueError, TypeError):
                    days_active = 0

                brand_item = QTableWidgetItem(str(ad.get("page_name", "")))
                industry_item = QTableWidgetItem(str(ad.get("industry") or "General"))
                days_item = QTableWidgetItem(str(days_active))
                cta_item = QTableWidgetItem(str(ad.get("hook_type") or "Other"))
                cod_item = QTableWidgetItem("Yes" if ad.get("has_cod") else "No")

                for cell in (brand_item, industry_item, days_item, cta_item, cod_item):
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.home_top_ads_table.setItem(row_idx, 0, brand_item)
                self.home_top_ads_table.setItem(row_idx, 1, industry_item)
                self.home_top_ads_table.setItem(row_idx, 2, days_item)
                self.home_top_ads_table.setItem(row_idx, 3, cta_item)
                self.home_top_ads_table.setItem(row_idx, 4, cod_item)

            self._clear_home_formula_cards()
            for ind in sorted(industries):
                winners = industry_winners.get(ind, [])
                if not winners:
                    self._add_home_formula_card(
                        f"{ind}: No winning ads (30+ days) found yet."
                    )
                    continue

                cta_counter = Counter(str(w.get("hook_type") or "Other") for w in winners)
                cod_winners = sum(1 for w in winners if w.get("has_cod"))
                top_hook = cta_counter.most_common(1)[0][0]
                cod_share = round(cod_winners / len(winners) * 100)
                avg_d = round(sum(
                    max(0, (now - _dt.fromisoformat(w["pulled_at"])).days)
                    for w in winners if w.get("pulled_at")
                ) / len(winners), 0)
                self._add_home_formula_card(
                    f"{ind}: {len(winners)} winners | Top hook: {top_hook} | "
                    f"{cod_share}% COD | Avg {int(avg_d)} days active"
                )

        except Exception as exc:
            print(f"Error refreshing home dashboard: {exc}")
            self.home_insight_text.setText(f"Error loading dashboard: {exc}")

    def _refresh_collection_stats(self) -> None:
        try:
            all_ads = get_all_ads()
            total = len(all_ads)
            self.coll_total_db_lbl.setText(f"Current DB Total: {total:,}")
        except Exception:
            pass

    def _on_start_collection(self) -> None:
        if self._collection_worker and self._collection_worker.isRunning():
            return

        selected_industries = []
        for btn in self.industry_toggles:
            if btn.isChecked():
                selected_industries.append(btn.text())

        if not selected_industries:
            self.coll_log_edit.append("Please select at least one industry to collect.")
            return

        self.start_coll_btn.setEnabled(False)
        self.stop_coll_btn.setEnabled(True)

        self.coll_progress_bar.setMaximum(len(selected_industries))
        self.coll_progress_bar.setValue(0)
        self.coll_status_table.setRowCount(0)
        self.coll_log_edit.clear()

        for row, ind in enumerate(selected_industries):
            self.coll_status_table.insertRow(row)
            self.coll_status_table.setItem(row, 0, QTableWidgetItem(ind))

            status_item = QTableWidgetItem("Waiting")
            status_item.setForeground(QColor("#9ca3af"))
            self.coll_status_table.setItem(row, 1, status_item)

            self.coll_status_table.setItem(row, 2, QTableWidgetItem("-"))
            self.coll_status_table.setItem(row, 3, QTableWidgetItem("-"))

        self._collection_worker = CollectionWorker(selected_industries)
        self._collection_worker.progress.connect(self._on_collection_progress)
        self._collection_worker.status_update.connect(self._on_collection_status_update)
        self._collection_worker.log_message.connect(self._on_collection_log)
        self._collection_worker.collection_finished.connect(self._on_collection_finished)
        self._collection_worker.error_occurred.connect(self._on_collection_error)
        self._collection_worker.start()

    def _on_stop_collection(self) -> None:
        if self._collection_worker and self._collection_worker.isRunning():
            self._collection_worker.cancel()
            self.stop_coll_btn.setEnabled(False)

    def _on_collection_progress(
        self,
        index: int,
        industry: str,
        found_count: int,
        saved_count: int,
    ) -> None:
        self.coll_progress_bar.setValue(index + 1)
        for row in range(self.coll_status_table.rowCount()):
            if self.coll_status_table.item(row, 0).text() == industry:
                status_item = QTableWidgetItem("Done")
                status_item.setForeground(QColor("#10b981"))
                self.coll_status_table.setItem(row, 1, status_item)
                self.coll_status_table.setItem(row, 2, QTableWidgetItem(str(found_count)))
                self.coll_status_table.setItem(row, 3, QTableWidgetItem(str(saved_count)))
                break

    def _on_collection_status_update(self, message: str) -> None:
        if message.startswith("Collecting "):
            ind = message.replace("Collecting ", "").replace("...", "")
            for row in range(self.coll_status_table.rowCount()):
                if self.coll_status_table.item(row, 0).text() == ind:
                    status_item = QTableWidgetItem("Running")
                    status_item.setForeground(QColor("#f59e0b"))
                    self.coll_status_table.setItem(row, 1, status_item)
                    break

    def _on_collection_log(self, message: str) -> None:
        self.coll_log_edit.append(message)
        # Scroll to bottom
        scrollbar = self.coll_log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_collection_finished(self) -> None:
        self.start_coll_btn.setEnabled(True)
        self.stop_coll_btn.setEnabled(False)
        self._refresh_home()
        self._refresh_collection_stats()
        from datetime import datetime
        now_str = datetime.now().strftime('%H:%M')
        self.coll_last_run_lbl.setText(f"Last Run: {now_str}")

        total_saved = 0
        for row in range(self.coll_status_table.rowCount()):
            saved_item = self.coll_status_table.item(row, 3)
            if saved_item and saved_item.text().isdigit():
                total_saved += int(saved_item.text())

        self.coll_collected_lbl.setText(f"Ads Collected Last Run: {total_saved}")

        log_time = datetime.now().strftime('%H:%M:%S')
        self.coll_log_edit.append(f"[{log_time}] Collection complete — {total_saved} new ads added to database")

    def _on_collection_error(self, error_msg: str) -> None:
        from datetime import datetime
        log_time = datetime.now().strftime('%H:%M:%S')
        self.coll_log_edit.append(f"[{log_time}] ERROR: {error_msg}")

    def _on_generate_clicked(self) -> None:
        """Handles 'Generate Report' button click by dispatching work to QThread."""
        industry = self.industry_combo.currentText()
        use_mock = self.demo_checkbox.isChecked()

        self.generate_button.setEnabled(False)
        self.generate_button.setText("Analyzing...")
        self.market_overview_status.setText(f"Fetching and analyzing ad intelligence for '{industry}'...")
        self.market_overview_status.setStyleSheet("color: #9ca3af; font-size: 14px;")

        # Switch to Market Overview page (index 3)
        self._switch_page(3)

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
        """Updates all pages with actual pipeline values, AI brief, and auto-saves report."""
        self._ads = ads
        self._offer_matrix = offer_matrix
        self._hook_report = hook_report
        self._brief = brief

        industry = self.industry_combo.currentText()

        # 1. Update Market Overview
        total_ads = len(ads)
        cod_rate = f"{offer_matrix.cod_prevalence_pct:.1f}%"
        dom_lang = str(hook_report.dominant_language)

        self.val_total_ads.setText(f"{total_ads:,}")
        self.val_cod_rate.setText(cod_rate)
        self.val_dom_lang.setText(dom_lang)

        # Survivor Ads KPI
        survivor_ads = get_survivor_ads(ads, min_days=30)
        survivor_count = len(survivor_ads)
        survivor_pct = (survivor_count / total_ads * 100) if total_ads > 0 else 0.0
        self.val_survivor_count.setText(f"{survivor_count:,}")
        self.val_survivor_pct.setText(f"{survivor_pct:.1f}%")

        self.survivor_table.setRowCount(0)
        for offer in offer_matrix.records:
            # Match offer detail to original ad to get days_active
            matching_ad = next(
                (ad for ad in survivor_ads if ad.ad_id == offer.ad_id or ad.page_name == offer.page_name), None
            )
            if matching_ad:
                row = self.survivor_table.rowCount()
                self.survivor_table.insertRow(row)
                p_item = QTableWidgetItem(offer.page_name)
                d_item = QTableWidgetItem(str(getattr(matching_ad, "days_active", 30)))
                cta_item = QTableWidgetItem(offer.primary_cta)
                cod_item = QTableWidgetItem("Yes" if offer.has_cash_on_delivery else "No")
                for cell in (p_item, d_item, cta_item, cod_item):
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.survivor_table.setItem(row, 0, p_item)
                self.survivor_table.setItem(row, 1, d_item)
                self.survivor_table.setItem(row, 2, cta_item)
                self.survivor_table.setItem(row, 3, cod_item)

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

        # Market Structure KPI
        cd = compute_competitive_density(ads)
        self.val_unique_advertisers.setText(str(cd["unique_advertisers"]))
        self.val_avg_ads_per_brand.setText(str(cd["avg_ads_per_brand"]))
        self.val_dominant_brand.setText(cd["dominant_brand"])
        top5 = cd["top_5_brands"]
        top_count = top5[0]["count"] if top5 else 0
        self.val_top_brand_count.setText(str(top_count))
        self.top5_brands_table.setRowCount(len(top5))
        for row, entry in enumerate(top5):
            name_cell = QTableWidgetItem(entry["page_name"])
            count_cell = QTableWidgetItem(str(entry["count"]))
            name_cell.setFlags(name_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            count_cell.setFlags(count_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.top5_brands_table.setItem(row, 0, name_cell)
            self.top5_brands_table.setItem(row, 1, count_cell)

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

        # Hook Saturation Index
        saturation = compute_hook_saturation(ads)
        self.saturation_table.setRowCount(0)
        status_colors = {
            "Oversaturated": ("#7f1d1d", "#fca5a5"),
            "Competitive":   ("#78350f", "#fcd34d"),
            "Opportunity":   ("#14532d", "#86efac"),
        }
        for sat_row, (hook_type, data) in enumerate(saturation.items()):
            self.saturation_table.insertRow(sat_row)
            ht_cell = QTableWidgetItem(hook_type)
            ct_cell = QTableWidgetItem(str(data["count"]))
            pct_cell = QTableWidgetItem(f"{data['percentage']}%")
            label = data["saturation_label"]
            st_cell = QTableWidgetItem(label)
            bg, fg = status_colors.get(label, ("#1e2130", "#ffffff"))
            st_cell.setBackground(QColor(bg))
            st_cell.setForeground(QColor(fg))
            for cell in (ht_cell, ct_cell, pct_cell, st_cell):
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.saturation_table.setItem(sat_row, 0, ht_cell)
            self.saturation_table.setItem(sat_row, 1, ct_cell)
            self.saturation_table.setItem(sat_row, 2, pct_cell)
            self.saturation_table.setItem(sat_row, 3, st_cell)

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
        self.export_pdf_button.setEnabled(True)

        # 5. Refresh Watchlist Stats
        self._refresh_watchlist_table()

        # 6. Auto-Save to Report History
        try:
            save_report(
                offer_matrix=offer_matrix,
                hook_report=hook_report,
                brief=brief,
                industry=industry,
                ads=ads,
            )
            self._refresh_history_table()
        except Exception as exc:
            print(f"Error auto-saving report to history: {exc}")

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


    def _refresh_season_breakdown(self) -> None:
        """Refreshes the seasonality breakdown table from the database."""
        try:
            rows = get_season_breakdown()
            self.season_table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                season_item = QTableWidgetItem(str(row.get("season", "regular")))
                count_item = QTableWidgetItem(str(row.get("count", 0)))
                for cell in (season_item, count_item):
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.season_table.setItem(row_idx, 0, season_item)
                self.season_table.setItem(row_idx, 1, count_item)
        except Exception as exc:
            print(f"Error refreshing season breakdown: {exc}")

    def _refresh_history_table(self) -> None:
        """Refreshes the history table with all saved reports from the database."""
        try:
            reports = get_report_history()
            self.history_count_label.setText(f"Saved reports: {len(reports)}")
            self.history_table.setRowCount(len(reports))

            for row_idx, r in enumerate(reports):
                d_item = QTableWidgetItem(str(r.get("generated_at") or "-"))
                ind_item = QTableWidgetItem(str(r.get("industry", "")))
                tot_item = QTableWidgetItem(str(r.get("total_ads", 0)))
                cod_val = r.get("cod_rate", 0.0)
                cod_item = QTableWidgetItem(f"{cod_val:.1f}%" if isinstance(cod_val, (int, float)) else str(cod_val))
                hook_item = QTableWidgetItem(str(r.get("dominant_hook", "")))
                angle_text = str(r.get("brief_angle", ""))
                angle_trunc = angle_text[:70] + ("..." if len(angle_text) > 70 else "")
                angle_item = QTableWidgetItem(angle_trunc)

                for it in (d_item, ind_item, tot_item, cod_item, hook_item, angle_item):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.history_table.setItem(row_idx, 0, d_item)
                self.history_table.setItem(row_idx, 1, ind_item)
                self.history_table.setItem(row_idx, 2, tot_item)
                self.history_table.setItem(row_idx, 3, cod_item)
                self.history_table.setItem(row_idx, 4, hook_item)
                self.history_table.setItem(row_idx, 5, angle_item)

                load_btn = QPushButton("Load")
                load_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #1d4ed8;
                    }
                """)
                load_btn.clicked.connect(lambda checked, rep=r: self._on_load_report_clicked(rep))
                self.history_table.setCellWidget(row_idx, 6, load_btn)

        except Exception as exc:
            print(f"Error refreshing history table: {exc}")

    def _on_load_report_clicked(self, report: Dict[str, Any]) -> None:
        """Loads a historical report from the database and repopulates the UI."""
        try:
            industry = report.get("industry", "General")
            total_ads = report.get("total_ads", 0)
            cod_rate = report.get("cod_rate", 0.0)
            dom_lang = report.get("dominant_language", "Unknown")
            dom_hook = report.get("dominant_hook", "Unknown")
            gen_at = report.get("generated_at", "")
            brief_angle = report.get("brief_angle", "")
            brief_ws = report.get("brief_whitespace", "")

            # Repopulate Market Overview
            self.val_total_ads.setText(f"{total_ads:,}")
            self.val_cod_rate.setText(f"{cod_rate:.1f}%" if isinstance(cod_rate, (int, float)) else str(cod_rate))
            self.val_dom_lang.setText(str(dom_lang))
            self.market_overview_status.setText(
                f"Loaded historical report for '{industry}' generated on {gen_at}. Total ads: {total_ads}."
            )
            self.market_overview_status.setStyleSheet("color: #3b82f6; font-size: 14px;")

            # Repopulate Hook Psychology
            self.val_dom_hook.setText(str(dom_hook))

            # Repopulate Strategy Playbook basic values
            self.val_brief_niche.setText(industry)
            self.val_brief_whitespace.setText(brief_ws or "Historical report gap analysis.")
            self.val_brief_angle.setText(brief_angle or "Historical psychological angle.")

            # If full report_json exists, restore offer matrix and brief hooks
            raw_json = report.get("report_json")
            if raw_json:
                try:
                    payload = json.loads(raw_json)
                    brief_data = payload.get("brief", {})
                    if isinstance(brief_data, dict):
                        if brief_data.get("recommended_offer_structure"):
                            self.val_brief_offer.setText(brief_data["recommended_offer_structure"])
                        if brief_data.get("suggested_hooks"):
                            self.hooks_list_widget.clear()
                            for idx, hook_text in enumerate(brief_data["suggested_hooks"], start=1):
                                self.hooks_list_widget.addItem(QListWidgetItem(f"Hook #{idx}: {hook_text}"))
                            self.export_button.setEnabled(True)

                    offer_data = payload.get("offer_matrix", {})
                    if isinstance(offer_data, dict):
                        self.val_cta.setText(offer_data.get("most_common_cta", "-"))
                        self.val_free_delivery.setText(f"{offer_data.get('free_shipping_prevalence_pct', 0.0):.1f}%")
                        self.val_offer_cod.setText(f"{offer_data.get('cod_prevalence_pct', 0.0):.1f}%")
                        pr_ranges = offer_data.get("price_ranges_detected", [])
                        self.val_price_ranges.setText(", ".join(pr_ranges) if pr_ranges else "None")

                        records = offer_data.get("records", [])
                        self.offer_table.setRowCount(len(records))
                        for row, rec in enumerate(records):
                            p_cell = QTableWidgetItem(rec.get("page_name", ""))
                            pr_cell = QTableWidgetItem(rec.get("price_mentioned") or "N/A")
                            c_cell = QTableWidgetItem("Yes" if rec.get("has_cash_on_delivery") else "No")
                            cta_cell = QTableWidgetItem(rec.get("primary_cta", "Other"))
                            for c in (p_cell, pr_cell, c_cell, cta_cell):
                                c.setFlags(c.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self.offer_table.setItem(row, 0, p_cell)
                            self.offer_table.setItem(row, 1, pr_cell)
                            self.offer_table.setItem(row, 2, c_cell)
                            self.offer_table.setItem(row, 3, cta_cell)

                    hook_data = payload.get("hook_report", {})
                    if isinstance(hook_data, dict):
                        items = hook_data.get("items", [])
                        self.hooks_table.setRowCount(0)
                        for row_idx, item in enumerate(items):
                            self.hooks_table.insertRow(row_idx)
                            raw_h = item.get("raw_hook", "")
                            raw_trunc = raw_h[:80] + ("..." if len(raw_h) > 80 else "")
                            p_item = QTableWidgetItem(item.get("page_name", ""))
                            h_item = QTableWidgetItem(item.get("hook_type", ""))
                            l_item = QTableWidgetItem(item.get("language", ""))
                            r_item = QTableWidgetItem(raw_trunc)
                            for c in (p_item, h_item, l_item, r_item):
                                c.setFlags(c.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self.hooks_table.setItem(row_idx, 0, p_item)
                            self.hooks_table.setItem(row_idx, 1, h_item)
                            self.hooks_table.setItem(row_idx, 2, l_item)
                            self.hooks_table.setItem(row_idx, 3, r_item)
                except Exception as json_err:
                    print(f"Error parsing historical report JSON payload: {json_err}")

            # Switch back to Market Overview to view loaded metrics
            self._switch_page(3)
        except Exception as exc:
            print(f"Error loading report: {exc}")

    def _refresh_new_entrants_table(self) -> None:
        """Refreshes the Trend Tracker new entrants table with brands seen for the first time this week."""
        try:
            entrants = get_new_entrants(days_back=7)
            self.new_entrants_count_label.setText(f"New entrants found: {len(entrants)}")
            self.new_entrants_table.setRowCount(len(entrants))
            for row_idx, entry in enumerate(entrants):
                brand_item = QTableWidgetItem(str(entry.get("page_name", "")))
                industry_item = QTableWidgetItem(str(entry.get("industry", "")))
                seen_raw = entry.get("first_seen") or ""
                seen_item = QTableWidgetItem(seen_raw[:10] if seen_raw else "-")
                ads_item = QTableWidgetItem(str(entry.get("ads_found", 0)))
                for it in (brand_item, industry_item, seen_item, ads_item):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.new_entrants_table.setItem(row_idx, 0, brand_item)
                self.new_entrants_table.setItem(row_idx, 1, industry_item)
                self.new_entrants_table.setItem(row_idx, 2, seen_item)
                self.new_entrants_table.setItem(row_idx, 3, ads_item)
        except Exception as exc:
            print(f"Error refreshing new entrants table: {exc}")

    def _on_brand_search(self) -> None:
        """Handles brand name search on Brand Profile page."""
        from datetime import datetime as _dt
        query = self.brand_search_input.text().strip()
        if not query:
            return

        try:
            all_ads = get_all_ads()
            matched = [
                ad for ad in all_ads
                if query.lower() in str(ad.get("page_name", "")).lower()
            ]

            total = len(matched)
            self.bp_val_total.setText(str(total))
            self.track_brand_button.setEnabled(total > 0)

            if total == 0:
                self.bp_val_avg_days.setText("-")
                self.bp_val_cta.setText("-")
                self.bp_val_cod.setText("-")
                self.brand_ads_table.setRowCount(0)
                return

            # Avg days active: days since pulled_at until now
            now = _dt.utcnow()
            days_list = []
            for ad in matched:
                pulled_raw = ad.get("pulled_at")
                if pulled_raw:
                    try:
                        pulled_dt = _dt.fromisoformat(pulled_raw)
                        days_list.append(max(0, (now - pulled_dt).days))
                    except ValueError:
                        pass
            avg_days = round(sum(days_list) / len(days_list), 1) if days_list else 0
            self.bp_val_avg_days.setText(str(avg_days))

            # Most used CTA
            cta_counter = Counter(
                str(ad.get("hook_type") or "Other") for ad in matched
            )
            top_cta = cta_counter.most_common(1)[0][0] if cta_counter else "-"
            self.bp_val_cta.setText(top_cta)

            # COD usage percentage
            cod_count = sum(1 for ad in matched if ad.get("has_cod"))
            cod_pct = round(cod_count / total * 100, 1) if total else 0
            self.bp_val_cod.setText(f"{cod_pct}%")

            # Populate table
            self.brand_ads_table.setRowCount(total)
            for row_idx, ad in enumerate(matched):
                pulled_raw = ad.get("pulled_at") or ""
                date_str = pulled_raw[:10] if pulled_raw else "-"
                ad_copy = str(ad.get("ad_copy") or "")
                copy_trunc = ad_copy[:100] + ("..." if len(ad_copy) > 100 else "")

                pulled_dt_val = None
                if pulled_raw:
                    try:
                        pulled_dt_val = _dt.fromisoformat(pulled_raw)
                    except ValueError:
                        pass
                days_active = max(0, (now - pulled_dt_val).days) if pulled_dt_val else 0

                has_cod_str = "Yes" if ad.get("has_cod") else "No"
                cta_str = str(ad.get("hook_type") or "Other")

                date_item = QTableWidgetItem(date_str)
                copy_item = QTableWidgetItem(copy_trunc)
                days_item = QTableWidgetItem(str(days_active))
                cod_item = QTableWidgetItem(has_cod_str)
                cta_item = QTableWidgetItem(cta_str)

                for it in (date_item, copy_item, days_item, cod_item, cta_item):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.brand_ads_table.setItem(row_idx, 0, date_item)
                self.brand_ads_table.setItem(row_idx, 1, copy_item)
                self.brand_ads_table.setItem(row_idx, 2, days_item)
                self.brand_ads_table.setItem(row_idx, 3, cod_item)
                self.brand_ads_table.setItem(row_idx, 4, cta_item)

        except Exception as exc:
            print(f"Error during brand search: {exc}")

    def _on_track_brand_clicked(self) -> None:
        """Adds the searched brand to the watchlist."""
        query = self.brand_search_input.text().strip()
        if not query:
            return
        try:
            add_to_watchlist(page_name=query, industry="General")
            self.track_brand_button.setEnabled(False)
            self.track_brand_button.setText("Tracked")
        except Exception as exc:
            print(f"Error adding brand to watchlist: {exc}")

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
