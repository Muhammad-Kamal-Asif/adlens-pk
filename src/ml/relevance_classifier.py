"""
RelevanceClassifier — ML-powered ad-industry relevance scoring.

Uses a TF-IDF + LogisticRegression pipeline trained on ads stored in the
local database.  Falls back to keyword matching from
``src.core.relevance`` when no trained model is available.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.core.schemas import RawAdRecord

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent / "models"
_MODEL_PATH = _MODEL_DIR / "relevance_model.pkl"
_FEEDBACK_PATH = _MODEL_DIR / "relevance_feedback.jsonl"

# Re-use the keyword dictionaries already defined in the codebase so the
# fallback path stays consistent with the rest of AdLens.
from src.core.relevance import INDUSTRY_KEYWORDS


class RelevanceClassifier:
    """Train, score, and filter ads by industry relevance."""

    def __init__(self) -> None:
        self._pipeline: Optional[Pipeline] = None
        self._classes: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train_from_db(self) -> float:
        """Train a TF-IDF + LogisticRegression pipeline on all DB ads.

        Incorporates any feedback logged in ``relevance_feedback.jsonl``
        as additional training signal.

        Returns the accuracy score on a held-out test split.
        """
        from src.db.repository import get_all_ads, init_db

        init_db()
        all_ads: List[Dict] = get_all_ads()

        if not all_ads:
            logger.warning("No ads in database — cannot train.")
            return 0.0

        texts: List[str] = []
        labels: List[str] = []

        for ad in all_ads:
            copy = (ad.get("ad_copy") or "").strip()
            industry = (ad.get("industry") or "").strip().lower().replace(" ", "_")
            if copy and industry:
                texts.append(copy)
                labels.append(industry)

        # Merge feedback --------------------------------------------------
        feedback_texts, feedback_labels = self._load_feedback()
        texts.extend(feedback_texts)
        labels.extend(feedback_labels)

        if len(texts) < 10:
            logger.warning(
                "Fewer than 10 training samples (%d) — model may be unreliable.",
                len(texts),
            )

        # Deduplicate labels that might have very few samples — sklearn's
        # LogisticRegression needs at least 2 classes.
        unique_labels = set(labels)
        if len(unique_labels) < 2:
            logger.warning(
                "Only %d unique industry label(s) found — need at least 2 to train.",
                len(unique_labels),
            )
            return 0.0

        # Build pipeline ---------------------------------------------------
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=8000,
                ngram_range=(1, 2),
                sublinear_tf=True,
                strip_accents="unicode",
                min_df=2,
                max_df=0.95,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=1.0,
                solver="lbfgs",
                class_weight="balanced",
            )),
        ])

        # Stratified split — fall back to shuffle split when classes are tiny
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=0.2, random_state=42, stratify=labels,
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=0.2, random_state=42,
            )

        pipeline.fit(X_train, y_train)
        accuracy = float(pipeline.score(X_test, y_test))

        # Retrain on full data for production model
        pipeline.fit(texts, labels)

        # Persist -----------------------------------------------------------
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, _MODEL_PATH)
        logger.info(
            "Model saved to %s  (accuracy=%.4f, samples=%d, classes=%d)",
            _MODEL_PATH, accuracy, len(texts), len(unique_labels),
        )

        self._pipeline = pipeline
        self._classes = pipeline.classes_

        return accuracy

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score(self, ad_copy: str, expected_industry: str) -> float:
        """Return probability (0.0-1.0) that *ad_copy* belongs to *expected_industry*.

        Falls back to keyword matching when no trained model exists.
        """
        industry_key = expected_industry.strip().lower().replace(" ", "_")

        # Try ML model first
        pipeline = self._get_pipeline()
        if pipeline is not None:
            try:
                probas = pipeline.predict_proba([ad_copy])[0]
                classes = list(pipeline.classes_)
                if industry_key in classes:
                    return float(probas[classes.index(industry_key)])
                # If the industry wasn't seen during training, return max proba
                return float(max(probas))
            except Exception as exc:
                logger.debug("ML scoring failed, falling back to keywords: %s", exc)

        # Fallback: keyword matching (mirrors src.core.relevance logic)
        return self._keyword_score(ad_copy, industry_key)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_relevant(
        self,
        ads: List[RawAdRecord],
        industry: str,
        threshold: float = 0.3,
    ) -> Tuple[List[RawAdRecord], List[RawAdRecord]]:
        """Score each ad and return ``(kept, filtered_out)``.

        * If fewer than 5 pass at *threshold*, retries at 0.1.
        * If still fewer than 3, returns all ads sorted by descending score.
        """
        if not ads:
            return [], []

        scored: List[Tuple[RawAdRecord, float]] = [
            (ad, self.score(ad.ad_copy, industry)) for ad in ads
        ]
        scored.sort(key=lambda t: t[1], reverse=True)

        def _split(thresh: float):
            kept = [ad for ad, s in scored if s >= thresh]
            out = [ad for ad, s in scored if s < thresh]
            return kept, out

        kept, out = _split(threshold)

        if len(kept) < 5:
            logger.info(
                "Only %d ads above %.2f — lowering threshold to 0.1", len(kept), threshold,
            )
            kept, out = _split(0.1)

        if len(kept) < 3:
            logger.info(
                "Still only %d ads above 0.1 — returning all %d sorted by score.",
                len(kept), len(scored),
            )
            kept = [ad for ad, _ in scored]
            out = []

        return kept, out

    # ------------------------------------------------------------------
    # Feedback logging
    # ------------------------------------------------------------------

    def log_feedback(
        self, ad_id: str, industry: str, was_relevant: bool,
        ad_copy: str = "",
    ) -> None:
        """Append a feedback record to the JSONL file."""
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ad_id": ad_id,
            "industry": industry,
            "was_relevant": was_relevant,
            "ad_copy": ad_copy,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(_FEEDBACK_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Could not write feedback: %s", exc)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_pipeline(self) -> Optional[Pipeline]:
        """Lazy-load the persisted model."""
        if self._pipeline is not None:
            return self._pipeline
        if _MODEL_PATH.exists():
            try:
                self._pipeline = joblib.load(_MODEL_PATH)
                return self._pipeline
            except Exception as exc:
                logger.warning("Could not load model from %s: %s", _MODEL_PATH, exc)
        return None

    def _load_feedback(self) -> Tuple[List[str], List[str]]:
        """Read the feedback JSONL and return (texts, labels).

        Positive feedback uses the logged industry as label.
        Negative feedback is skipped (removing bad examples rather than
        creating a synthetic "not-X" class keeps the label space clean).
        """
        texts: List[str] = []
        labels: List[str] = []
        if not _FEEDBACK_PATH.exists():
            return texts, labels
        try:
            with open(_FEEDBACK_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("was_relevant") and rec.get("ad_copy"):
                        industry = (rec.get("industry") or "general").strip().lower().replace(" ", "_")
                        texts.append(rec["ad_copy"])
                        labels.append(industry)
        except Exception as exc:
            logger.warning("Error reading feedback file: %s", exc)
        return texts, labels

    @staticmethod
    def _keyword_score(ad_copy: str, industry_key: str) -> float:
        """Keyword-based fallback score (same logic as ``src.core.relevance``)."""
        keywords = INDUSTRY_KEYWORDS.get(industry_key, INDUSTRY_KEYWORDS.get("general", []))
        if not keywords:
            return 0.0
        ad_lower = ad_copy.lower()
        matches = sum(
            1 for kw in keywords
            if re.search(rf"\b{re.escape(kw.lower())}\b", ad_lower)
        )
        return float(matches) / len(keywords)
