"""
ML Training Center page for AdLens PK desktop UI.
Displays model status, triggers manual retrains, and shows training logs.
"""

from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ml.scheduler_hook import get_model_status, trigger_manual_retrain


class _RetrainWorker(QThread):
    finished = pyqtSignal(dict)

    def run(self) -> None:
        result = trigger_manual_retrain()
        self.finished.emit(result)


class MLTrainingPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: Optional[_RetrainWorker] = None
        self._build_ui()
        self.refresh_status()

    # ── UI construction ───────────────────────────────────────────────────────

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

        # Header
        header = QLabel("ML Training Center")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        sub = QLabel("Manage and monitor the AdLens classification model training pipeline.")
        sub.setStyleSheet("color: #9ca3af; font-size: 14px;")
        layout.addWidget(sub)

        # Status metric cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(18)

        self._card_status, self._val_status = self._make_card("Model Status", "Checking...")
        self._card_trained, self._val_trained = self._make_card("Last Trained", "Never")
        self._card_records, self._val_records = self._make_card("Training Records", "0")

        for card, _ in (self._card_status, self._card_trained, self._card_records):
            cards_row.addWidget(card)
        layout.addLayout(cards_row)

        # Accuracy label
        self._accuracy_label = QLabel("Model Accuracy: —")
        self._accuracy_label.setStyleSheet(
            "color: #10b981; font-size: 15px; font-weight: 600;"
        )
        layout.addWidget(self._accuracy_label)

        # Manual retrain button + progress bar
        retrain_row = QHBoxLayout()
        self._retrain_btn = QPushButton("Manual Retrain")
        self._retrain_btn.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #d62828; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """)
        self._retrain_btn.clicked.connect(self._on_retrain_clicked)
        retrain_row.addWidget(self._retrain_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(22)
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e2130;
                border: 1px solid #2d3148;
                border-radius: 6px;
                color: #ffffff;
                text-align: center;
            }
            QProgressBar::chunk { background-color: #e63946; border-radius: 6px; }
        """)
        retrain_row.addWidget(self._progress, 1)
        layout.addLayout(retrain_row)

        # Next scheduled retrain
        self._next_retrain_label = QLabel("Next Scheduled Retrain: —")
        self._next_retrain_label.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(self._next_retrain_label)

        # Training log
        log_title = QLabel("Training Log")
        log_title.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; margin-bottom: 12px;"
        )
        layout.addWidget(log_title)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(180)
        self._log.setStyleSheet(
            "background-color: #1e2130; color: #d1d5db; border: 1px solid #2d3148;"
            " border-radius: 8px; padding: 8px; font-family: monospace; font-size: 12px;"
        )
        layout.addWidget(self._log, 1)

        # Note section
        self._note_label = QLabel()
        self._note_label.setWordWrap(True)
        self._note_label.setStyleSheet(
            "color: #6b7280; font-size: 12px; font-style: italic;"
        )
        layout.addWidget(self._note_label)
        self._update_note(db_records=0, kaggle_records=0)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_card(self, title: str, default: str):
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
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(8)

        t = QLabel(title)
        t.setStyleSheet(
            "color: #9ca3af; font-size: 12px; font-weight: 600;"
            " border: none; background: transparent;"
        )
        v = QLabel(default)
        vf = QFont()
        vf.setPointSize(18)
        vf.setBold(True)
        v.setFont(vf)
        v.setStyleSheet("color: #ffffff; border: none; background: transparent;")

        cl.addWidget(t)
        cl.addWidget(v)
        return (card, v), v

    def _update_note(self, db_records: int, kaggle_records: int) -> None:
        self._note_label.setText(
            f"Model improves automatically as more ads are collected. "
            f"Currently using {db_records} records from database + "
            f"{kaggle_records} records from Kaggle datasets."
        )

    def _log_line(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}] {text}")

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh_status(self) -> None:
        """Re-read status.json and update all status widgets."""
        status = get_model_status()

        # Model Status card
        if status["model_exists"]:
            self._val_status.setText("Trained")
            self._val_status.setStyleSheet(
                "color: #10b981; border: none; background: transparent;"
            )
        else:
            self._val_status.setText("Not Trained")
            self._val_status.setStyleSheet(
                "color: #e63946; border: none; background: transparent;"
            )

        # Last Trained card
        lt: Optional[datetime] = status["last_trained"]
        self._val_trained.setText(lt.strftime("%Y-%m-%d %H:%M") if lt else "Never")

        # Training Records card
        self._val_records.setText(str(status["training_records"]))

        # Accuracy label
        acc = status["model_accuracy"]
        if acc is not None:
            self._accuracy_label.setText(f"Model Accuracy: {float(acc):.2%}")
        else:
            self._accuracy_label.setText("Model Accuracy: —")

        # Next scheduled retrain (7 days from last training, or unknown)
        if lt:
            next_run: datetime = lt + timedelta(days=7)
            self._next_retrain_label.setText(
                f"Next Scheduled Retrain: {next_run.strftime('%Y-%m-%d %H:%M UTC')}"
            )
        else:
            self._next_retrain_label.setText("Next Scheduled Retrain: Not yet scheduled")

        # Update note with DB count
        try:
            from src.db.repository import get_all_ads
            db_count = len(get_all_ads())
        except Exception:
            db_count = status["training_records"]
        self._update_note(db_records=db_count, kaggle_records=0)

    # ── Slot ──────────────────────────────────────────────────────────────────

    def _on_retrain_clicked(self) -> None:
        self._retrain_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log_line("Manual retrain requested...")

        self._worker = _RetrainWorker()
        self._worker.finished.connect(self._on_retrain_finished)
        self._worker.start()

    def _on_retrain_finished(self, result: dict) -> None:
        self._progress.setVisible(False)
        self._retrain_btn.setEnabled(True)

        if result.get("success"):
            self._log_line(
                f"Retrain complete — "
                f"records: {result['records_used']}, "
                f"accuracy: {float(result['accuracy']):.2%}, "
                f"duration: {result['duration_seconds']}s, "
                f"model: {result['model_path']}"
            )
        else:
            self._log_line(f"Retrain FAILED — {result.get('error', 'unknown error')}")

        self.refresh_status()
