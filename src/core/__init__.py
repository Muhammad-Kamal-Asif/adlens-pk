"""
AdLens PK — Core Business Logic Package
"""
from src.core.schemas import (
    RawAdRecord,
    AdOfferDetails,
    OfferMatrixSummary,
    HookItem,
    HookAnalysisReport,
    TacticalCreativeBrief,
)
from src.core.fetcher import fetch_ads
from src.core.extractor import extract_offer_details, build_offer_matrix
from src.core.classifier import detect_language, extract_raw_hook, classify_single_hook, analyze_hooks
from src.core.ai_engine import generate_tactical_brief
from src.core.database import init_db, save_ads, get_all_ads
from src.core.kaggle_enricher import load_kaggle_demand, get_demand_context, download_kaggle_dataset

__all__ = [
    "RawAdRecord",
    "AdOfferDetails",
    "OfferMatrixSummary",
    "HookItem",
    "HookAnalysisReport",
    "TacticalCreativeBrief",
    "fetch_ads",
    "extract_offer_details",
    "build_offer_matrix",
    "detect_language",
    "extract_raw_hook",
    "classify_single_hook",
    "analyze_hooks",
    "generate_tactical_brief",
    "init_db",
    "save_ads",
    "get_all_ads",
    "load_kaggle_demand",
    "get_demand_context",
    "download_kaggle_dataset",
]
