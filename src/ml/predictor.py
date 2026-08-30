"""Production AdLens PK ad-copy predictor.

Loads a trained classifier and fitted AdFeatureBuilder from `src/ml/models/` and
scores ad copy on a 0-100 scale. Falls back to `ready=False` when model artifacts
are missing so callers can prompt the user to train first.
"""

import pickle
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.ml.feature_builder import AdFeatureBuilder


MODEL_DIR = Path(__file__).resolve().parent / "models"
CLASSIFIER_PATH = MODEL_DIR / "adlens_classifier.pkl"
FEATURE_BUILDER_PATH = MODEL_DIR / "feature_builder.pkl"


def _extract_cta_type(ad_copy: str) -> str:
    """Extract a simple CTA type from raw ad copy."""
    lower = ad_copy.lower()
    if "whatsapp" in lower or "message" in lower:
        return "Send WhatsApp Message"
    if "shop" in lower or "buy" in lower:
        return "Shop Now"
    if "order" in lower:
        return "Order Now"
    if "call" in lower:
        return "Call Now"
    if "learn" in lower:
        return "Learn More"
    return "Other"


class AdPredictor:
    """
    Loads trained artifacts and predicts ad-copy performance.

    Expected artifacts (pickled by src.ml.trainer):
      - models/adlens_classifier.pkl : fitted sklearn classifier with predict_proba
      - models/feature_builder.pkl   : fitted AdFeatureBuilder
    """

    def __init__(self) -> None:
        self._classifier: Optional[object] = None
        self._feature_builder: Optional[AdFeatureBuilder] = None
        self.ready = False
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        if not CLASSIFIER_PATH.exists() or not FEATURE_BUILDER_PATH.exists():
            self.ready = False
            return

        try:
            with open(CLASSIFIER_PATH, "rb") as fh:
                self._classifier = pickle.load(fh)
            with open(FEATURE_BUILDER_PATH, "rb") as fh:
                self._feature_builder = pickle.load(fh)
            self.ready = True
        except Exception:
            self._classifier = None
            self._feature_builder = None
            self.ready = False

    def is_ready(self) -> bool:
        """Return True when trained model artifacts are available."""
        return self.ready

    def _compute_score(self, features) -> int:
        """Convert classifier output to a 0-100 integer score."""
        if hasattr(self._classifier, "predict_proba"):
            proba = self._classifier.predict_proba(features)
            # Assume positive class is the last column (strong / high-performing)
            score = int(round(proba[0][-1] * 100))
        elif hasattr(self._classifier, "predict"):
            raw = self._classifier.predict(features)
            val = raw[0]
            # Regressor: clip to [0, 100]; classifier label: map boolean-ish to 0/100
            if isinstance(val, (int, float)):
                score = int(round(max(0.0, min(100.0, float(val)))))
            else:
                score = 100 if str(val).lower() in ("1", "true", "strong", "good", "high") else 0
        else:
            score = 50
        return score

    def _generate_feedback(
        self,
        ad_copy: str,
        industry: str,
        has_cod: bool,
        mentions_price: bool,
        score: int,
    ) -> List[str]:
        """Generate human-readable feedback based on input signals and score."""
        text = ad_copy.strip()
        lower = text.lower()
        words = re.findall(r"\b[a-z]+\b", lower)
        word_count = len(words)
        feedback: List[str] = []

        if score >= 70:
            feedback.append("Model predicts strong performance for this copy")
        elif score >= 40:
            feedback.append("Model predicts average performance; room to improve")
        else:
            feedback.append("Model predicts weak performance; consider a rewrite")

        if 15 <= word_count <= 60:
            feedback.append("Optimal ad copy length for feed placements")
        elif word_count < 10:
            feedback.append("Ad copy is very short; expand the hook and offer")
        elif word_count > 100:
            feedback.append("Ad copy is long; front-load the key message")

        if has_cod or re.search(r"\b(cash on delivery|cod|payment on delivery)\b", lower):
            feedback.append("Cash on delivery reduces buyer friction")
        else:
            feedback.append("No COD mention; consider adding risk reversal")

        if mentions_price or re.search(r"(?:rs\.?|pkr)\s?[0-9,]+", lower):
            feedback.append("Price mention improves conversion clarity")
        else:
            feedback.append("No price detected; shoppers may hesitate")

        if re.search(r"\b(fauri|jaldi|limited stock|ending soon|aaj hi|last chance|hurry|abhi)\b", lower):
            feedback.append("Urgency / scarcity trigger present")
        else:
            feedback.append("Add urgency words to drive faster action")

        roman_urdu_words = {
            "karein", "karo", "hai", "hain", "apna", "apni", "aap", "bhi",
            "yeh", "woh", "ke", "ki", "ka", "ko", "se", "par", "mein",
            "fauri", "bachat", "asli", "muft", "sasta", "behtareen",
            "rabta", "mangwayen", "dastiyab", "aaj", "hi", "kya", "aap",
        }
        if sum(1 for w in words if w in roman_urdu_words) >= 3:
            feedback.append("Roman-Urdu vernacular hook resonates locally")
        else:
            feedback.append("Consider Roman-Urdu phrasing for local relevance")

        if re.search(r"\b(order|shop|buy|call|message|whatsapp|send|book)\b", lower):
            feedback.append("Direct call-to-action detected")
        else:
            feedback.append("Add a clear call-to-action (Order/Shop/Call)")

        if re.search(
            r"\b(\d+\+?\s*(customers|students|reviews|clients|users|buyers|families|orders)|trust|trusted|authentic|verified)\b",
            lower,
        ):
            feedback.append("Social proof signal builds credibility")

        if re.search(r"\b(flat|\d+%\s*off|sale|discount|free delivery|chhoot)\b", lower):
            feedback.append("Offer / discount language detected")

        return feedback

    def predict(
        self,
        ad_copy: str,
        industry: str,
        has_cod: bool,
        mentions_price: bool,
    ) -> Dict[str, object]:
        """
        Score ad copy using the trained model.

        Raises RuntimeError if model artifacts are not loaded. Callers should
        check `is_ready()` first.
        """
        if not self.ready or self._classifier is None or self._feature_builder is None:
            raise RuntimeError("Model not loaded. Train the model first.")

        df = pd.DataFrame([{
            "ad_copy": ad_copy,
            "industry": industry.lower().replace(" & ", "_").replace(" ", "_"),
            "cta_type": _extract_cta_type(ad_copy),
            "has_cod": bool(has_cod),
            "has_price": bool(mentions_price),
        }])

        features = self._feature_builder.transform(df)
        score = self._compute_score(features)

        if score >= 70:
            label = "Strong"
        elif score >= 40:
            label = "Average"
        else:
            label = "Weak"

        feedback = self._generate_feedback(ad_copy, industry, has_cod, mentions_price, score)

        return {"score": score, "label": label, "feedback": feedback}
