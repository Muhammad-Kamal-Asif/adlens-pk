"""
AdLens PK — Relational Persistence Engine (SQLAlchemy)
Stores ingested and processed ad records into an SQLite/PostgreSQL database.
"""

from datetime import datetime
from typing import List, Optional
import os

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import settings
from src.core.schemas import RawAdRecord

Base = declarative_base()


class AdModel(Base):
    """SQLAlchemy ORM model mapping to the raw ad records."""
    __tablename__ = "ads"

    ad_id = Column(String, primary_key=True, index=True)
    page_name = Column(String, nullable=False, index=True)
    ad_copy = Column(Text, nullable=False)
    media_type = Column(String, default="image")
    cta_raw = Column(String, nullable=True, default="LEARN_MORE")
    days_active = Column(Integer, default=1)
    industry = Column(String, nullable=False, index=True)
    source_type = Column(String, default="curated_seed")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_schema(self) -> RawAdRecord:
        """Converts ORM model to validated Pydantic schema."""
        return RawAdRecord(
            ad_id=self.ad_id,
            page_name=self.page_name,
            ad_copy=self.ad_copy,
            media_type=self.media_type,
            cta_raw=self.cta_raw,
            days_active=self.days_active,
            industry=self.industry,
            source_type=self.source_type,
        )


def get_engine(db_url: Optional[str] = None):
    url = db_url or settings.DATABASE_URL or "sqlite:///adlens.db"
    return create_engine(url, echo=False)


def get_session_factory(db_url: Optional[str] = None):
    engine = get_engine(db_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(db_url: Optional[str] = None) -> None:
    """Creates all database tables if they do not exist."""
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)


def save_ads(records: List[RawAdRecord], db_url: Optional[str] = None) -> int:
    """
    Saves or updates a list of RawAdRecord instances in the database.
    Returns the count of records saved.
    """
    if not records:
        return 0

    init_db(db_url)
    session_factory = get_session_factory(db_url)
    saved_count = 0

    with session_factory() as session:
        for rec in records:
            ad_obj = session.get(AdModel, rec.ad_id)
            if ad_obj:
                ad_obj.page_name = rec.page_name
                ad_obj.ad_copy = rec.ad_copy
                ad_obj.media_type = rec.media_type
                ad_obj.cta_raw = rec.cta_raw
                ad_obj.days_active = rec.days_active
                ad_obj.industry = rec.industry
                ad_obj.source_type = rec.source_type
            else:
                ad_obj = AdModel(
                    ad_id=rec.ad_id,
                    page_name=rec.page_name,
                    ad_copy=rec.ad_copy,
                    media_type=rec.media_type,
                    cta_raw=rec.cta_raw,
                    days_active=rec.days_active,
                    industry=rec.industry,
                    source_type=rec.source_type,
                )
                session.add(ad_obj)
            saved_count += 1
        session.commit()

    return saved_count


def get_all_ads(industry: Optional[str] = None, db_url: Optional[str] = None) -> List[RawAdRecord]:
    """
    Retrieves all ads from the database, optionally filtered by industry.
    Returns a list of RawAdRecord Pydantic models.
    """
    init_db(db_url)
    session_factory = get_session_factory(db_url)

    with session_factory() as session:
        stmt = select(AdModel)
        if industry and industry.lower() != "general":
            stmt = stmt.where(AdModel.industry.ilike(f"%{industry}%"))
        results = session.scalars(stmt).all()
        return [ad.to_schema() for ad in results]
