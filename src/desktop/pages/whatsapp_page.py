import logging
from typing import List, Dict, Any, Tuple, Optional
import pyqtgraph as pg

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.whatsapp_analyzer import (
    analyze_whatsapp_patterns,
    get_whatsapp_insight,
)
from src.db.repository import get_all_ads
from src.core.fetcher import fetch_ads

logger = logging.getLogger(__name__)


class WhatsAppAnalyzerPage(QWidget):
    """
    Dedicated analytical view for WhatsApp direct-response advertising intelligence,
    Pakistani commercial phone number extraction, and longevity metrics.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
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

        # Header Title & Description
        header_label = QLabel("WhatsApp CTA Intelligence")
        header_font = QFont("Inter", 24, QFont.Weight.Bold)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        sub_label = QLabel(
            "Evaluation of WhatsApp conversational commerce adoption, direct phone number extraction, "
            "and ad longevity comparisons across Pakistani commercial niches."
        )
        sub_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        sub_label.setWordWrap(True)
        layout.addWidget(sub_label)

        # 1. Four Metric Cards Row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        card_adopt, self.val_adoption = self._create_metric_card(
            "WhatsApp Adoption %", "-", "Prevalence of direct WhatsApp funnels", "#25D366"
        )
        card_ratio, self.val_ratio = self._create_metric_card(
            "WhatsApp vs Website", "-", "Direct chat vs online store ratio", "#ffffff"
        )
        card_days_wa, self.val_days_wa = self._create_metric_card(
            "Avg Days Active (WhatsApp)", "-", "Longevity of WhatsApp ad creatives", "#10b981"
        )
        card_days_non, self.val_days_non = self._create_metric_card(
            "Avg Days Active (Non-WA)", "-", "Longevity of traditional web ads", "#22c55e"
        )

        cards_layout.addWidget(card_adopt)
        cards_layout.addWidget(card_ratio)
        cards_layout.addWidget(card_days_wa)
        cards_layout.addWidget(card_days_non)
        layout.addLayout(cards_layout)

        # 2. Strategic Insight Card
        insight_frame = QFrame()
        insight_frame.setStyleSheet("""
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
        insight_layout = QVBoxLayout(insight_frame)
        insight_layout.setContentsMargins(16, 12, 16, 12)
        insight_layout.setSpacing(6)

        insight_title = QLabel("STRATEGIC CHANNEL INSIGHT")
        insight_title.setStyleSheet("color: #25D366; font-size: 12px; font-weight: 700; text-transform: uppercase;")
        insight_layout.addWidget(insight_title)

        self.insight_label = QLabel("Analyzing WhatsApp conversational advertising patterns...")
        self.insight_label.setStyleSheet("color: #ffffff; font-size: 14px; line-height: 1.4;")
        self.insight_label.setWordWrap(True)
        insight_layout.addWidget(self.insight_label)

        layout.addWidget(insight_frame)

        # 3. Bar Chart: WhatsApp Adoption by Industry
        chart_title = QLabel("WhatsApp Adoption by Industry")
        chart_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(chart_title)

        self.industry_chart = pg.PlotWidget(title="WhatsApp Ad Count by Industry")
        self.industry_chart.setBackground("#1e2130")
        self.industry_chart.getAxis("left").setPen(pg.mkPen(color="#9ca3af"))
        self.industry_chart.getAxis("bottom").setPen(pg.mkPen(color="#9ca3af"))
        self.industry_chart.setFixedHeight(200)
        self.industry_chart.setMouseEnabled(x=False, y=False)
        self.industry_chart.hideButtons()
        self.industry_chart.setMenuEnabled(False)
        self.industry_chart.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.industry_chart.getViewBox().wheelEvent = lambda ev: ev.ignore()
        layout.addWidget(self.industry_chart)

        # 4. Table: Sample WhatsApp Ads
        table_title = QLabel("Sample WhatsApp Ad Creatives & Extracted Phone Numbers")
        table_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(table_title)

        self.sample_table = QTableWidget()
        self.sample_table.setAlternatingRowColors(True)
        self.sample_table.setStyleSheet(
            "QTableWidget { gridline-color: #2d3148; alternate-background-color: #1a1d27; } "
            "QHeaderView::section { background-color: #1e2130; color: #9ca3af; "
            "font-size: 11px; font-weight: 600; padding: 6px; border: none; }"
        )
        self.sample_table.setColumnCount(4)
        self.sample_table.setHorizontalHeaderLabels([
            "Page Name",
            "Phone Number",
            "Days Active",
            "Ad Copy (80 chars)",
        ])
        self.sample_table.horizontalHeader().setStretchLastSection(True)
        self.sample_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.sample_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.sample_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.sample_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.sample_table.setColumnWidth(0, 180)
        self.sample_table.setColumnWidth(1, 160)
        self.sample_table.verticalHeader().setVisible(False)
        self.sample_table.setMinimumHeight(220)
        layout.addWidget(self.sample_table, 1)

    def _create_metric_card(
        self, title: str, default_value: str, subtitle: str, highlight_color: str = "#ffffff"
    ) -> Tuple[QFrame, QLabel]:
        """Creates a styled QFrame metric card."""
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
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 600; border: none; background: transparent;")

        val_label = QLabel(default_value)
        val_font = QFont("Inter", 24, QFont.Weight.Bold)
        val_label.setFont(val_font)
        val_label.setStyleSheet(f"color: {highlight_color}; border: none; background: transparent;")
        val_label.setWordWrap(True)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("color: #6b7280; font-size: 12px; border: none; background: transparent;")

        card_layout.addWidget(title_label)
        card_layout.addWidget(val_label)
        card_layout.addWidget(sub_label)

        return card, val_label

    def refresh(self) -> None:
        """
        Reloads ad records from database (or mock dataset if database is fresh) and updates all visual elements.
        """
        try:
            records = get_all_ads()
            if not records:
                records = fetch_ads(industry="general", use_mock=True)

            patterns = analyze_whatsapp_patterns(records)

            # Update Metric Cards
            adoption_pct = patterns.get("whatsapp_adoption_pct", 0.0)
            self.val_adoption.setText(f"{adoption_pct:.1f}%")
            self.val_ratio.setText(patterns.get("whatsapp_vs_website_ratio", "0:0"))
            self.val_days_wa.setText(f"{patterns.get('avg_days_active_whatsapp', 0.0):.1f}d")
            self.val_days_non.setText(f"{patterns.get('avg_days_active_non_whatsapp', 0.0):.1f}d")

            # Update Strategic Insight
            insight_text = get_whatsapp_insight(adoption_pct)
            self.insight_label.setText(insight_text)

            # Update Industry Chart
            self.industry_chart.clear()
            top_industries = patterns.get("top_whatsapp_industries", [])
            if top_industries:
                names = [item["industry"] for item in top_industries]
                counts = [item["count"] for item in top_industries]
                x_pos = list(range(len(names)))

                bg = pg.BarGraphItem(x=x_pos, height=counts, width=0.6, brush="#25D366")
                self.industry_chart.addItem(bg)
                ticks = [[(i, n) for i, n in enumerate(names)]]
                self.industry_chart.getAxis("bottom").setTicks(ticks)

            # Update Sample Ads Table
            sample_ads = patterns.get("sample_whatsapp_ads", [])
            self.sample_table.setRowCount(len(sample_ads))
            for row_idx, ad in enumerate(sample_ads):
                p_item = QTableWidgetItem(str(ad.get("page_name", "")))
                ph_item = QTableWidgetItem(str(ad.get("whatsapp_number", "-")))
                d_item = QTableWidgetItem(str(ad.get("days_active", 1)))
                c_item = QTableWidgetItem(str(ad.get("ad_copy", "")))

                for it in (p_item, ph_item, d_item, c_item):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.sample_table.setItem(row_idx, 0, p_item)
                self.sample_table.setItem(row_idx, 1, ph_item)
                self.sample_table.setItem(row_idx, 2, d_item)
                self.sample_table.setItem(row_idx, 3, c_item)

        except Exception as exc:
            logger.error(f"Error refreshing WhatsAppAnalyzerPage: {exc}")
