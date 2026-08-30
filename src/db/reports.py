import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    select,
)

from src.db.models import Base, engine, SessionLocal

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SavedReport(Base):
    __tablename__ = "saved_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    industry = Column(String(100), nullable=False)
    generated_at = Column(DateTime, default=_utc_now)
    total_ads = Column(Integer, default=0)
    cod_rate = Column(Float, default=0.0)
    dominant_language = Column(String(50), nullable=True)
    dominant_hook = Column(String(100), nullable=True)
    avg_days_active = Column(Float, default=0.0)
    brief_angle = Column(Text, nullable=True)
    brief_whitespace = Column(Text, nullable=True)
    report_json = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "industry": self.industry,
            "generated_at": self.generated_at.strftime("%Y-%m-%d %H:%M") if self.generated_at else None,
            "total_ads": self.total_ads or 0,
            "cod_rate": self.cod_rate or 0.0,
            "dominant_language": self.dominant_language or "Unknown",
            "dominant_hook": self.dominant_hook or "Unknown",
            "avg_days_active": self.avg_days_active or 0.0,
            "brief_angle": self.brief_angle or "",
            "brief_whitespace": self.brief_whitespace or "",
            "report_json": self.report_json,
        }


def save_report(
    offer_matrix: Any,
    hook_report: Any,
    brief: Any,
    industry: str = "General",
    ads: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Saves a generated analysis report to the database.
    Extracts summary metrics and serializes full pipeline data to JSON for historical loading.
    """
    Base.metadata.create_all(bind=engine)

    total_ads = len(ads) if ads else (getattr(offer_matrix, "total_ads_evaluated", 0) if offer_matrix else 0)
    cod_rate = float(getattr(offer_matrix, "cod_prevalence_pct", 0.0)) if offer_matrix else 0.0
    dominant_language = str(getattr(hook_report, "dominant_language", "Unknown")) if hook_report else "Unknown"
    dominant_hook = str(getattr(hook_report, "dominant_hook_type", "Unknown")) if hook_report else "Unknown"

    avg_days = 0.0
    if ads and len(ads) > 0:
        avg_days = sum(getattr(a, "days_active", 1) for a in ads) / len(ads)

    brief_angle = str(getattr(brief, "recommended_angle", "")) if brief else ""
    brief_whitespace = str(getattr(brief, "market_whitespace", "")) if brief else ""

    # Build full serializable payload
    payload = {
        "industry": industry,
        "total_ads": total_ads,
        "cod_rate": cod_rate,
        "dominant_language": dominant_language,
        "dominant_hook": dominant_hook,
        "avg_days_active": avg_days,
        "brief": brief.model_dump() if hasattr(brief, "model_dump") else (brief if isinstance(brief, dict) else str(brief)),
        "offer_matrix": offer_matrix.model_dump() if hasattr(offer_matrix, "model_dump") else (offer_matrix if isinstance(offer_matrix, dict) else str(offer_matrix)),
        "hook_report": hook_report.model_dump() if hasattr(hook_report, "model_dump") else (hook_report if isinstance(hook_report, dict) else str(hook_report)),
        "ads": [a.model_dump() if hasattr(a, "model_dump") else a for a in (ads or [])],
    }

    try:
        report_json_str = json.dumps(payload, default=str)
    except Exception as exc:
        logger.warning(f"Failed to serialize report payload to JSON: {exc}")
        report_json_str = "{}"

    with SessionLocal() as session:
        report_entity = SavedReport(
            industry=industry,
            generated_at=_utc_now(),
            total_ads=total_ads,
            cod_rate=cod_rate,
            dominant_language=dominant_language,
            dominant_hook=dominant_hook,
            avg_days_active=avg_days,
            brief_angle=brief_angle,
            brief_whitespace=brief_whitespace,
            report_json=report_json_str,
        )
        session.add(report_entity)
        session.commit()
        session.refresh(report_entity)
        logger.info(f"Saved analysis report #{report_entity.id} for industry '{industry}'.")
        return report_entity.to_dict()


def get_report_history() -> List[Dict[str, Any]]:
    """
    Retrieves all saved reports in chronological descending order.
    Returns list of dicts representing historical reports.
    """
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stmt = select(SavedReport).order_by(SavedReport.generated_at.desc(), SavedReport.id.desc())
        records = session.scalars(stmt).all()
        return [r.to_dict() for r in records]


def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single saved report by its ID.
    """
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stmt = select(SavedReport).where(SavedReport.id == report_id)
        record = session.scalars(stmt).first()
        if record:
            return record.to_dict()
        return None
