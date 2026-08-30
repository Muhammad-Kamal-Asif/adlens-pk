"""One-shot patch: adds the Trend Tracker page (index 4) to main_window.py."""
path = "C:/Users/Asif Computers/Desktop/adlens-pk/src/desktop/main_window.py"

with open(path, encoding="utf-8") as f:
    src = f.read()

# Guard: skip if already patched
if "TrendDataWorker" in src:
    print("Already patched.")
    raise SystemExit(0)

# 1. Expand typing import
src = src.replace(
    "from typing import List, Optional, Tuple\n",
    "from typing import Any, Dict, List, Optional, Tuple\n",
    1,
)

# 2. Add new imports after ai_engine
src = src.replace(
    "from src.core.ai_engine import generate_tactical_brief\n",
    (
        "from src.core.ai_engine import generate_tactical_brief\n"
        "from src.core.kaggle_enricher import get_demand_context\n"
        "from src.db.repository import get_all_ads, get_trend_data\n"
        "\n"
        "import pandas as pd\n"
    ),
    1,
)

# 3. Insert TrendDataWorker class right before AdLensPKWindow
TREND_WORKER = '''

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

'''
src = src.replace(
    "\nclass AdLensPKWindow(QMainWindow):\n",
    TREND_WORKER + "\nclass AdLensPKWindow(QMainWindow):\n",
    1,
)

# 4. Add _trend_worker instance var to __init__
src = src.replace(
    "        self._worker: Optional[AdFetchWorker] = None\n"
    "        self._ads: List[RawAdRecord] = []\n",
    "        self._worker: Optional[AdFetchWorker] = None\n"
    "        self._trend_worker: Optional[TrendDataWorker] = None\n"
    "        self._ads: List[RawAdRecord] = []\n",
    1,
)

# 5. Wire industry combo signal
src = src.replace(
    "        self.industry_combo.addItems(self.industry_options)\n"
    "        layout.addWidget(self.industry_combo)\n",
    "        self.industry_combo.addItems(self.industry_options)\n"
    "        self.industry_combo.currentTextChanged.connect(self._refresh_trend_tracker)\n"
    "        layout.addWidget(self.industry_combo)\n",
    1,
)

# 6. Insert Trend Tracker page builder + helpers before _build_content_stack
TREND_PAGE_METHODS = '''    def _build_trend_tracker_page(self) -> QWidget:
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
            "Trend data builds over time \\u2014 run the app daily to see patterns emerge."
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
            placeholder = QTableWidgetItem("No data yet \\u2014 generate a report first.")
            placeholder.setForeground(QColor("#6b7280"))
            self.trend_table.setItem(0, 0, placeholder)

    def _on_trend_data_error(self, error_msg: str) -> None:
        self.trend_demand_label.setText(f"Error loading trend data: {error_msg}")
        self.trend_demand_label.setStyleSheet(
            "background-color: #1e2130; border: 1px solid #e63946;"
            " border-left: 3px solid #e63946; border-radius: 8px;"
            " color: #e63946; font-size: 13px; padding: 14px 16px;"
        )

'''
src = src.replace(
    "    def _build_content_stack(self) -> QStackedWidget:\n",
    TREND_PAGE_METHODS + "    def _build_content_stack(self) -> QStackedWidget:\n",
    1,
)

# 7. Replace scaffold call for page 4 with real builder + initial load
src = src.replace(
    "        # Page 4: Trend Tracker (Scaffold)\n"
    "        stack.addWidget(self._build_scaffold_page(\"Trend Tracker\"))\n"
    "\n"
    "        return stack\n",
    "        # Page 4: Trend Tracker\n"
    "        stack.addWidget(self._build_trend_tracker_page())\n"
    "\n"
    "        # Kick off initial data load\n"
    "        self._refresh_trend_tracker()\n"
    "\n"
    "        return stack\n",
    1,
)

# 8. Refresh Trend Tracker when user navigates to it
src = src.replace(
    "    def _switch_page(self, index: int) -> None:\n"
    "        self.content_stack.setCurrentIndex(index)\n"
    "        for i, btn in enumerate(self.nav_buttons):\n"
    "            btn.setChecked(i == index)\n",
    "    def _switch_page(self, index: int) -> None:\n"
    "        self.content_stack.setCurrentIndex(index)\n"
    "        for i, btn in enumerate(self.nav_buttons):\n"
    "            btn.setChecked(i == index)\n"
    "        if index == 4:\n"
    "            self._refresh_trend_tracker()\n",
    1,
)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched successfully. Total lines: {src.count(chr(10))}")
