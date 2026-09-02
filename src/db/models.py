import os
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./adlens_local.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AdRecord(Base):
    __tablename__ = "ad_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(255), unique=True, index=True, nullable=False)
    page_name = Column(String(255), nullable=False)
    ad_copy = Column(Text, nullable=False)
    industry = Column(String(100), nullable=False)
    source_type = Column(String(50), default="curated_seed")
    has_cod = Column(Boolean, default=False)
    price_mentioned = Column(String(100), nullable=True)
    dominant_language = Column(String(50), nullable=True)
    hook_type = Column(String(100), nullable=True)
    season_tag = Column(String(50), default="regular")
    pulled_at = Column(DateTime, default=datetime.utcnow)
    days_active = Column(Integer, nullable=True, default=None)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ad_id": self.ad_id,
            "page_name": self.page_name,
            "ad_copy": self.ad_copy,
            "industry": self.industry,
            "source_type": self.source_type,
            "has_cod": self.has_cod,
            "price_mentioned": self.price_mentioned,
            "dominant_language": self.dominant_language,
            "hook_type": self.hook_type,
            "season_tag": self.season_tag,
            "pulled_at": self.pulled_at.isoformat() if self.pulled_at else None,
            "days_active": self.days_active,
        }
