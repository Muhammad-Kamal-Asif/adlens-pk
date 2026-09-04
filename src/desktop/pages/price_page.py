from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.price_intelligence import (
    compute_price_bands,
    extract_all_prices,
    get_price_positioning,
    load_kaggle_price_data,
)
from src.core.schemas import RawAdRecord
from src.db.repository import get_all_ads


def _make_card(title: str, default: str, subtitle: str):
    """Dark metric card matching the main_window theme."""
    card = QFrame()
    card.setStyleSheet("""
        QFrame {
            background-color: #1e2130;
            border-radius: 10px;
            border-left: 3px solid #22c55e;
            border-top: 1px solid #2d3148;
            border-right: 1px solid #2d3148;
            border-bottom: 1px solid #2d3148;
            padding: 16px;
        }
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(8)

    t_label = QLabel(title)
    t_label.setStyleSheet(
        "color: #9ca3af; font-size: 13px; font-weight: 600;"
        " border: none; background: transparent;"
    )

    v_label = QLabel(default)
    v_font = QFont()
    v_font.setPointSize(22)
    v_font.setBold(True)
    v_label.setFont(v_font)
    v_label.setStyleSheet("color: #ffffff; border: none; background: transparent;")
    v_label.setWordWrap(True)

    s_label = QLabel(subtitle)
    s_label.setStyleSheet(
        "color: #6b7280; font-size: 12px; border: none; background: transparent;"
    )

    layout.addWidget(t_label)
    layout.addWidget(v_label)
    layout.addWidget(s_label)
    return card, v_label


class PriceIntelligencePage(QWidget):
    """
    Standalone PKR Price Intelligence page.
    Reads live ads from the DB + Kaggle CSVs to compute price bands
    and offers a personal price-positioning checker.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_prices: List[float] = []
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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

        # --- Header ---
        header = QLabel("PKR Price Intelligence")
        hf = QFont()
        hf.setPointSize(24)
        hf.setBold(True)
        header.setFont(hf)
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        sub = QLabel(
            "Market pricing landscape across Pakistani digital ads — "
            "band distribution, range, and competitive positioning."
        )
        sub.setStyleSheet("color: #9ca3af; font-size: 14px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self._status_label = QLabel("Loading price data…")
        self._status_label.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(self._status_label)

        # --- Three metric cards ---
        cards_row = QHBoxLayout()
        cards_row.setSpacing(18)

        card_median, self._val_median = _make_card(
            "Median Market Price", "—", "Middle price point across all ads"
        )
        card_range, self._val_range = _make_card(
            "Price Range", "—", "Lowest to highest detected price"
        )
        card_coverage, self._val_coverage = _make_card(
            "Ads With Price", "—", "% of ads that mention a PKR price"
        )

        cards_row.addWidget(card_median)
        cards_row.addWidget(card_range)
        cards_row.addWidget(card_coverage)
        layout.addLayout(cards_row)

        # --- Price band table ---
        band_title = QLabel("Price Band Distribution")
        btf = QFont()
        btf.setPointSize(16)
        btf.setBold(True)
        band_title.setFont(btf)
        band_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(band_title)

        self._band_table = QTableWidget(0, 3)
        self._band_table.setAlternatingRowColors(True)
        self._band_table.setStyleSheet(
            "QTableWidget { gridline-color: #2d3148; alternate-background-color: #1a1d27; } "
            "QHeaderView::section { background-color: #1e2130; color: #9ca3af; "
            "font-size: 11px; font-weight: 600; padding: 6px; border: none; }"
        )
        self._band_table.setHorizontalHeaderLabels(
            ["Band", "Ad Count", "Market Share %"]
        )
        self._band_table.horizontalHeader().setStretchLastSection(True)
        self._band_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._band_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._band_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._band_table.verticalHeader().setVisible(False)
        self._band_table.setFixedHeight(230)
        layout.addWidget(self._band_table)

        # --- Your Price Checker ---
        checker_title = QLabel("Your Price Checker")
        ctf = QFont()
        ctf.setPointSize(16)
        ctf.setBold(True)
        checker_title.setFont(ctf)
        checker_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(checker_title)

        checker_sub = QLabel(
            "Enter your product price in PKR to see where it sits in the market."
        )
        checker_sub.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(checker_sub)

        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self._price_input = QLineEdit()
        self._price_input.setPlaceholderText("Enter your price in PKR (e.g. 1499)")
        self._price_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e2130;
                color: #ffffff;
                border: 1px solid #2d3148;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #22c55e; }
        """)
        self._price_input.returnPressed.connect(self._on_check_clicked)
        input_row.addWidget(self._price_input, 1)

        self._check_btn = QPushButton("Check Position")
        self._check_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #16a34a; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """)
        self._check_btn.clicked.connect(self._on_check_clicked)
        input_row.addWidget(self._check_btn)

        layout.addLayout(input_row)

        self._result_card = QFrame()
        self._result_card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border-radius: 10px;
                border-left: 3px solid #22c55e;
                border-top: 1px solid #2d3148;
                border-right: 1px solid #2d3148;
                border-bottom: 1px solid #2d3148;
                padding: 16px;
            }
        """)
        result_layout = QVBoxLayout(self._result_card)
        result_layout.setContentsMargins(20, 16, 20, 16)
        result_layout.setSpacing(10)

        self._result_label = QLabel(
            "Enter a price above and click 'Check Position' to see your market positioning."
        )
        self._result_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self._result_label.setWordWrap(True)

        self._positioning_badge = QLabel("")
        pf = QFont()
        pf.setPointSize(18)
        pf.setBold(True)
        self._positioning_badge.setFont(pf)
        self._positioning_badge.setStyleSheet(
            "color: #ffffff; border: none; background: transparent;"
        )
        self._positioning_badge.hide()

        result_layout.addWidget(self._result_label)
        result_layout.addWidget(self._positioning_badge)

        layout.addWidget(self._result_card)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Data loading and refresh
    # ------------------------------------------------------------------

    def refresh(self):
        """Load prices from DB ads + Kaggle CSVs and repopulate all widgets."""
        # 1. Prices from live DB ads (via ad_copy regex)
        db_ads_raw = get_all_ads()
        db_records = [
            RawAdRecord(
                page_name=a.get("page_name", ""),
                ad_copy=a.get("ad_copy", ""),
                industry=a.get("industry", "general"),
            )
            for a in db_ads_raw
            if a.get("ad_copy")
        ]
        db_prices = extract_all_prices(db_records)
        total_db_ads = len(db_records)

        # 2. Prices from Kaggle CSVs
        kaggle_prices = load_kaggle_price_data()

        # Combined set for band display; keep DB prices for coverage metric
        all_prices = db_prices + kaggle_prices
        self._all_prices = all_prices

        # 3. Populate metric cards
        stats = compute_price_bands(all_prices)

        if all_prices:
            self._val_median.setText(f"Rs. {stats['median_price']:,.0f}")
            self._val_range.setText(
                f"Rs. {stats['min_price']:,.0f} — Rs. {stats['max_price']:,.0f}"
            )
        else:
            self._val_median.setText("N/A")
            self._val_range.setText("N/A")

        if total_db_ads > 0:
            coverage_pct = round(len(db_prices) / total_db_ads * 100, 1)
            self._val_coverage.setText(f"{coverage_pct}%")
        else:
            self._val_coverage.setText("0%")

        # 4. Populate band table
        bands = stats["price_bands"]
        self._band_table.setRowCount(len(bands))
        for row, band in enumerate(bands):
            label_item = QTableWidgetItem(band["label"])
            count_item = QTableWidgetItem(str(band["count"]))
            pct_item = QTableWidgetItem(f"{band['percentage']}%")
            for item in (label_item, count_item, pct_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            label_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            self._band_table.setItem(row, 0, label_item)
            self._band_table.setItem(row, 1, count_item)
            self._band_table.setItem(row, 2, pct_item)

        # 5. Status line
        src_note = []
        if db_prices:
            src_note.append(f"{len(db_prices)} prices from {total_db_ads} DB ads")
        if kaggle_prices:
            src_note.append(f"{len(kaggle_prices)} prices from Kaggle CSVs")
        if src_note:
            self._status_label.setText("Data sources: " + " · ".join(src_note))
            self._status_label.setStyleSheet("color: #10b981; font-size: 13px;")
        else:
            self._status_label.setText(
                "No price data found. Generate a report or check that Kaggle CSVs "
                "contain a 'price' column."
            )
            self._status_label.setStyleSheet("color: #f59e0b; font-size: 13px;")

    # ------------------------------------------------------------------
    # Checker interaction
    # ------------------------------------------------------------------

    def _on_check_clicked(self):
        raw = self._price_input.text().strip().replace(",", "")
        try:
            your_price = float(raw)
            if your_price <= 0:
                raise ValueError
        except ValueError:
            self._result_label.setText(
                "Please enter a valid positive number (e.g. 1499)."
            )
            self._result_label.setStyleSheet("color: #f59e0b; font-size: 14px;")
            self._positioning_badge.hide()
            return

        if not self._all_prices:
            self._result_label.setText(
                "No market price data available to compare against. "
                "Generate a report first."
            )
            self._result_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
            self._positioning_badge.hide()
            return

        pos = get_price_positioning(your_price, self._all_prices)
        label = pos["positioning_label"]
        percentile = pos["percentile"]
        comp_count = pos["competitive_count"]

        label_colours = {
            "Premium":   "#22c55e",
            "Mid-range": "#f59e0b",
            "Budget":    "#10b981",
        }
        colour = label_colours.get(label, "#ffffff")

        self._positioning_badge.setText(label)
        self._positioning_badge.setStyleSheet(
            f"color: {colour}; font-size: 18px; font-weight: 700;"
            " border: none; background: transparent;"
        )
        self._positioning_badge.show()

        self._result_label.setText(
            f"Rs. {your_price:,.0f} is cheaper than {percentile}% of market prices "
            f"({comp_count} ad{'s' if comp_count != 1 else ''} priced within ±20% of yours)."
        )
        self._result_label.setStyleSheet("color: #ffffff; font-size: 14px;")
