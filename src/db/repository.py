import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, func, cast, Date

from src.core.schemas import RawAdRecord
from src.db.models import engine, SessionLocal, Base, AdRecord
from src.db.watchlist import WatchlistEntry
from src.core.extractor import extract_offer_details
from src.core.classifier import detect_language, extract_raw_hook, classify_single_hook

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create all database tables defined in the ORM schema."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")


def save_ads(records: List[RawAdRecord]) -> int:
    """
    Save a list of RawAdRecord objects into the database.
    Upserts / inserts using ad_id as the unique key, silently skipping existing duplicates.
    Returns the count of newly saved records.
    """
    if not records:
        return 0

    init_db()

    inserted_count = 0
    with SessionLocal() as session:
        try:
            ad_ids = [
                r.ad_id if isinstance(r, RawAdRecord) else r.get("ad_id")
                for r in records
                if r
            ]
            ad_ids = [aid for aid in ad_ids if aid]

            existing_ids = set()
            if ad_ids:
                existing_stmt = select(AdRecord.ad_id).where(AdRecord.ad_id.in_(ad_ids))
                existing_ids = set(session.scalars(existing_stmt).all())

            new_entries = []
            for item in records:
                if not item:
                    continue

                if isinstance(item, RawAdRecord):
                    record_dict = item.model_dump()
                elif isinstance(item, dict):
                    record_dict = item
                else:
                    continue

                ad_id = str(record_dict.get("ad_id", "")).strip()
                if not ad_id or ad_id in existing_ids:
                    continue

                page_name = str(record_dict.get("page_name", "Unknown"))
                ad_copy = str(record_dict.get("ad_copy", ""))
                industry = str(record_dict.get("industry", "general"))
                source_type = str(record_dict.get("source_type", "curated_seed"))

                has_cod = False
                price_mentioned = None
                dominant_language = None
                hook_type = None

                try:
                    raw_record_obj = item if isinstance(item, RawAdRecord) else RawAdRecord(**record_dict)
                    offer_info = extract_offer_details(raw_record_obj)
                    has_cod = offer_info.has_cash_on_delivery
                    price_mentioned = offer_info.price_mentioned
                except Exception as e:
                    logger.debug(f"Offer extraction failed for ad {ad_id}: {e}")

                try:
                    dominant_language = detect_language(ad_copy)
                    raw_hook = extract_raw_hook(ad_copy)
                    hook_type = classify_single_hook(raw_hook)
                except Exception as e:
                    logger.debug(f"Hook/language classification failed for ad {ad_id}: {e}")

                ad_entity = AdRecord(
                    ad_id=ad_id,
                    page_name=page_name,
                    ad_copy=ad_copy,
                    industry=industry,
                    source_type=source_type,
                    has_cod=has_cod,
                    price_mentioned=price_mentioned,
                    dominant_language=dominant_language,
                    hook_type=hook_type,
                    season_tag="regular",
                    pulled_at=datetime.utcnow(),
                )

                new_entries.append(ad_entity)
                existing_ids.add(ad_id)

            if new_entries:
                session.add_all(new_entries)
                session.commit()
                inserted_count = len(new_entries)
                logger.info(f"Saved {inserted_count} new ad records to database.")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save ads to database: {e}")
            raise

    return inserted_count


def get_all_ads() -> List[Dict[str, Any]]:
    """Retrieve all stored ad records from the database as a list of dicts."""
    init_db()
    with SessionLocal() as session:
        stmt = select(AdRecord).order_by(AdRecord.id.desc())
        records = session.scalars(stmt).all()
        return [record.to_dict() for record in records]


def get_trend_data() -> List[Dict[str, Any]]:
    """
    Retrieve ad counts grouped by pulled_at date.
    Returns a list of dicts with 'date' and 'count' keys.
    """
    init_db()
    with SessionLocal() as session:
        date_expr = func.date(AdRecord.pulled_at)
        stmt = (
            session.query(
                date_expr.label("date"),
                func.count(AdRecord.id).label("count")
            )
            .group_by(date_expr)
            .order_by(date_expr.asc())
        )
        rows = stmt.all()
        return [{"date": str(row[0]), "count": int(row[1])} for row in rows]
