import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Any, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.repository import get_all_ads

_INDUSTRIES = [
    "fashion",
    "electronics",
    "health",
    "food",
    "real_estate",
    "education",
    "home",
    "general",
]

_COD_KEYWORDS = [
    "cash on delivery", "cod", "cashondelivery",
    "payment on delivery", "pay on delivery",
]

_CTA_PATTERNS = [
    ("Shop Now", re.compile(r"shop\s*now", re.IGNORECASE)),
    ("Send Message", re.compile(r"send\s*message|message\s*us", re.IGNORECASE)),
    ("Get Offer", re.compile(r"get\s*offer|grab\s*now|order\s*now|buy\s*now", re.IGNORECASE)),
    ("Contact Us", re.compile(r"contact\s*us|call\s*now|whatsapp", re.IGNORECASE)),
    ("Learn More", re.compile(r"learn\s*more", re.IGNORECASE)),
    ("Sign Up", re.compile(r"sign\s*up|register", re.IGNORECASE)),
]

_PRICE_RE = re.compile(r"(?:rs\.?|pkr)\s*([\d,]+)", re.IGNORECASE)


def _compute_days_active(ad: Dict[str, Any]) -> int:
    da = ad.get("days_active")
    if da and int(da) > 0:
        return int(da)
    pulled_at = ad.get("pulled_at")
    if pulled_at:
        try:
            dt = datetime.fromisoformat(pulled_at) if isinstance(pulled_at, str) else pulled_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(1, (datetime.now(timezone.utc) - dt).days)
        except Exception:
            pass
    return 1


def _detect_cod(ad: Dict[str, Any]) -> bool:
    if ad.get("has_cod"):
        return True
    copy = (ad.get("ad_copy") or "").lower()
    return any(kw in copy for kw in _COD_KEYWORDS)


def _detect_cta(ad: Dict[str, Any]) -> str:
    cta = ad.get("cta_raw") or ad.get("primary_cta") or ""
    if cta and cta != "unknown":
        return cta
    copy = ad.get("ad_copy") or ""
    for label, pattern in _CTA_PATTERNS:
        if pattern.search(copy):
            return label
    return "None"


def _extract_price(ad: Dict[str, Any]) -> int | None:
    pm = ad.get("price_mentioned")
    if pm:
        m = _PRICE_RE.search(str(pm))
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
    copy = ad.get("ad_copy") or ""
    m = _PRICE_RE.search(copy)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _detect_hook(ad: Dict[str, Any]) -> str:
    hook = ad.get("hook_type")
    if hook and hook != "unknown":
        return hook
    copy = (ad.get("ad_copy") or "")[:200].lower()
    if "?" in copy[:80]:
        return "Question"
    if any(w in copy for w in ["free", "discount", "sale", "off", "%", "deal"]):
        return "Offer/Discount"
    if any(w in copy for w in ["new", "launch", "just arrived", "introducing"]):
        return "Novelty"
    if any(w in copy for w in ["limited", "hurry", "last chance", "ending soon"]):
        return "Urgency"
    return "Direct"


_COMBO_STYLE = """
    QComboBox {
        background-color: #1e2130;
        color: #ffffff;
        border: 1px solid #2d3148;
        border-radius: 8px;
        padding: 8px 12px;
        min-height: 20px;
    }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox QAbstractItemView {
        background-color: #1e2130;
        color: #ffffff;
        selection-background-color: #e63946;
        border: 1px solid #2d3148;
    }
"""

_TABLE_STYLE = """
    QTableWidget {
        background-color: #1e2130;
        color: #ffffff;
        border: 1px solid #2d3148;
        border-radius: 8px;
        gridline-color: #2d3148;
    }
    QTableWidget::item { padding: 8px; }
    QHeaderView::section {
        background-color: #171924;
        color: #9ca3af;
        border: none;
        border-bottom: 1px solid #2d3148;
        padding: 10px 8px;
        font-weight: 600;
    }
"""


class WinningFormulaPage(QWidget):

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._on_industry_changed()
        self.industry_combo.currentTextChanged.connect(self._on_industry_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel("Winning Ad Formula")
        hf = QFont()
        hf.setPointSize(24)
        hf.setBold(True)
        header.setFont(hf)
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        subtitle = QLabel("What Pakistani ads running 30+ days have in common")
        subtitle.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(subtitle)

        self.industry_combo = QComboBox()
        self.industry_combo.addItems(_INDUSTRIES)
        self.industry_combo.setStyleSheet(_COMBO_STYLE)
        layout.addWidget(self.industry_combo)

        self.formula_card = QFrame()
        self.formula_card.setStyleSheet("""
            QFrame {
                background-color: #1e2130;
                border: 1px solid #2d3148;
                border-left: 4px solid #e63946;
                border-radius: 8px;
            }
        """)
        cl = QVBoxLayout(self.formula_card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(8)

        self.formula_title = QLabel("Formula")
        tf = QFont()
        tf.setPointSize(12)
        tf.setBold(True)
        self.formula_title.setFont(tf)
        self.formula_title.setStyleSheet("color: #e63946; background: transparent; border: none;")
        cl.addWidget(self.formula_title)

        self.formula_text = QLabel("")
        self.formula_text.setWordWrap(True)
        self.formula_text.setStyleSheet("color: #ffffff; font-size: 15px; background: transparent; border: none;")
        cl.addWidget(self.formula_text)

        self.stats_text = QLabel("")
        self.stats_text.setWordWrap(True)
        self.stats_text.setStyleSheet("color: #9ca3af; font-size: 13px; background: transparent; border: none;")
        cl.addWidget(self.stats_text)

        layout.addWidget(self.formula_card)

        self.table_label = QLabel("Winner Ads")
        tlf = QFont()
        tlf.setPointSize(14)
        tlf.setBold(True)
        self.table_label.setFont(tlf)
        self.table_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Page Name", "Days Active", "Has COD", "CTA", "Ad Copy (first 80 chars)"
        ])
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(250)
        layout.addWidget(self.table)

        layout.addStretch()

    def _on_industry_changed(self) -> None:
        industry = self.industry_combo.currentText().lower()
        all_ads = get_all_ads()

        industry_ads: List[Dict[str, Any]] = []
        for ad in all_ads:
            if (ad.get("industry") or "").lower() == industry:
                ad["_days_active"] = _compute_days_active(ad)
                industry_ads.append(ad)

        winners = [a for a in industry_ads if a["_days_active"] >= 30]

        if len(winners) < 3:
            self.formula_title.setText("Insufficient Data")
            self.formula_text.setText(
                "Not enough data yet -- run collection to build this intelligence"
            )
            self.stats_text.setText(
                f"Found {len(winners)} ads running 30+ days in {industry}. Need at least 3."
            )
            self.table.setRowCount(0)
            self.table_label.setText(f"Winner Ads ({len(winners)} found)")
            return

        cod_count = sum(1 for a in winners if _detect_cod(a))
        cod_pct = cod_count / len(winners) * 100
        cod_label = "COD offered" if cod_pct >= 50 else "No COD emphasis"

        cta_counts = Counter(_detect_cta(a) for a in winners)
        top_cta = cta_counts.most_common(1)[0][0]

        prices = [_extract_price(a) for a in winners]
        prices = [p for p in prices if p is not None]
        price_label = f"PKR {sum(prices)/len(prices):,.0f} avg price" if prices else "No price mentions"

        hook_counts = Counter(_detect_hook(a) for a in winners)
        top_hook = hook_counts.most_common(1)[0][0]

        copy_lens = [len(a.get("ad_copy") or "") for a in winners]
        avg_copy = sum(copy_lens) / len(copy_lens) if copy_lens else 0

        self.formula_title.setText(f"Winning Formula for {industry.title()}")
        self.formula_text.setText(
            f"In {industry.title()}, winning ads use: "
            f"{cod_label}, {top_cta} CTA, {price_label}, {top_hook} hooks"
        )
        self.stats_text.setText(
            f"Based on {len(winners)} ads running 30+ days. "
            f"COD prevalence: {cod_pct:.0f}%. "
            f"Average copy length: {avg_copy:.0f} chars."
        )

        self.table_label.setText(f"Winner Ads ({len(winners)} ads)")
        sorted_winners = sorted(winners, key=lambda a: a["_days_active"], reverse=True)
        self.table.setRowCount(len(sorted_winners))
        for row, ad in enumerate(sorted_winners):
            self.table.setItem(row, 0, QTableWidgetItem(ad.get("page_name", "Unknown")))
            self.table.setItem(row, 1, QTableWidgetItem(str(ad["_days_active"])))
            self.table.setItem(row, 2, QTableWidgetItem("Yes" if _detect_cod(ad) else "No"))
            self.table.setItem(row, 3, QTableWidgetItem(_detect_cta(ad)))
            copy_preview = (ad.get("ad_copy") or "")[:80].replace("\n", " ")
            self.table.setItem(row, 4, QTableWidgetItem(copy_preview))
