import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    select,
    func,
)

from src.db.models import Base, engine, SessionLocal

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_name = Column(String(255), unique=True, index=True, nullable=False)
    industry = Column(String(100), nullable=False, default="General")
    added_at = Column(DateTime, default=_utc_now)
    last_seen_at = Column(DateTime, nullable=True)
    total_ads_found = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "page_name": self.page_name,
            "industry": self.industry,
            "added_at": self.added_at.strftime("%Y-%m-%d %H:%M") if self.added_at else None,
            "last_seen_at": self.last_seen_at.strftime("%Y-%m-%d %H:%M") if self.last_seen_at else "Never",
            "total_ads_found": self.total_ads_found or 0,
            "is_active": self.is_active,
        }


def add_to_watchlist(page_name: str, industry: str = "General") -> Dict[str, Any]:
    """
    Adds a page name to the competitor watchlist.
    If the entry already exists, ensures is_active is set to True and updates industry.
    """
    clean_name = page_name.strip()
    clean_industry = industry.strip() if industry else "General"
    if not clean_name:
        raise ValueError("Page name cannot be empty.")

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stmt = select(WatchlistEntry).where(
            func.lower(WatchlistEntry.page_name) == clean_name.lower()
        )
        entry = session.scalars(stmt).first()
        if entry:
            entry.is_active = True
            if clean_industry and clean_industry != "General":
                entry.industry = clean_industry
            session.commit()
            session.refresh(entry)
            logger.info(f"Reactivated watchlist entry: {clean_name}")
            return entry.to_dict()
        else:
            new_entry = WatchlistEntry(
                page_name=clean_name,
                industry=clean_industry,
                added_at=_utc_now(),
                total_ads_found=0,
                is_active=True,
            )
            session.add(new_entry)
            session.commit()
            session.refresh(new_entry)
            logger.info(f"Added new watchlist entry: {clean_name} ({clean_industry})")
            return new_entry.to_dict()


def remove_from_watchlist(page_name: str) -> bool:
    """Removes a page name from the competitor watchlist."""
    clean_name = page_name.strip()
    if not clean_name:
        return False

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stmt = select(WatchlistEntry).where(
            func.lower(WatchlistEntry.page_name) == clean_name.lower()
        )
        entry = session.scalars(stmt).first()
        if entry:
            session.delete(entry)
            session.commit()
            logger.info(f"Removed watchlist entry: {clean_name}")
            return True
        return False


def get_watchlist(active_only: bool = True) -> List[Dict[str, Any]]:
    """Retrieves all watchlist entries from the database."""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stmt = select(WatchlistEntry)
        if active_only:
            stmt = stmt.where(WatchlistEntry.is_active.is_(True))
        stmt = stmt.order_by(WatchlistEntry.added_at.desc())
        entries = session.scalars(stmt).all()
        return [e.to_dict() for e in entries]


def update_watchlist_stats(page_name: str, ad_count: int) -> Optional[Dict[str, Any]]:
    """
    Updates last_seen_at to now and increments total_ads_found for a watchlist entry.
    """
    clean_name = page_name.strip()
    if not clean_name:
        return None

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stmt = select(WatchlistEntry).where(
            func.lower(WatchlistEntry.page_name) == clean_name.lower()
        )
        entry = session.scalars(stmt).first()
        if entry:
            entry.last_seen_at = _utc_now()
            entry.total_ads_found = (entry.total_ads_found or 0) + max(0, ad_count)
            session.commit()
            session.refresh(entry)
            logger.info(
                f"Updated watchlist stats for '{clean_name}': +{ad_count} ads (total: {entry.total_ads_found})"
            )
            return entry.to_dict()
        return None


def check_and_update_watchlist(records: List[Any]) -> Dict[str, int]:
    """
    Scans a list of ad records (RawAdRecord or dict), checks if any page_name matches
    an active watchlist entry, and calls update_watchlist_stats() with the count found.
    Returns a dict mapping matched page_name to the count found.
    """
    if not records:
        return {}

    try:
        active_entries = get_watchlist(active_only=True)
        if not active_entries:
            return {}

        # Build lookup table: lower_case_name -> canonical_name
        watchlist_lookup = {
            e["page_name"].strip().lower(): e["page_name"]
            for e in active_entries
            if e.get("page_name")
        }

        # Count matches
        matched_counts: Dict[str, int] = {}
        for rec in records:
            if not rec:
                continue
            p_name = getattr(rec, "page_name", None)
            if not p_name and isinstance(rec, dict):
                p_name = rec.get("page_name")

            if p_name:
                p_clean = str(p_name).strip().lower()
                if p_clean in watchlist_lookup:
                    canonical = watchlist_lookup[p_clean]
                    matched_counts[canonical] = matched_counts.get(canonical, 0) + 1

        # Update stats in db
        for canonical_name, count in matched_counts.items():
            update_watchlist_stats(canonical_name, count)

        return matched_counts
    except Exception as exc:
        logger.warning(f"Error scanning records for watchlist matches: {exc}")
        return {}
