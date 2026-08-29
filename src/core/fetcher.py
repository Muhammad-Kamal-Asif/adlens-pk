import json
import logging
from pathlib import Path
from typing import List, Optional
import requests

from src.config.settings import settings
from src.core.schemas import RawAdRecord

logger = logging.getLogger(__name__)

MOCK_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_ads.json"

INDUSTRY_SEARCH_TERMS = {
    "fashion": [
        "fashion", "clothing", "lawn", "dress", "unstitched", "shoes",
        "kapray", "kurti", "jora", "poshak", "bachat sale"
    ],
    "food": [
        "food delivery", "restaurant", "deals", "cafe", "fast food",
        "khana", "mithai", "biryani", "lazeez", "nashta", "dawat"
    ],
    "electronics": [
        "electronics", "mobile phone", "laptop", "smart watch", "gadgets", "earbuds",
        "sasta mobile", "chargers", "accessories"
    ],
    "real_estate": [
        "real estate", "property", "plot for sale", "commercial plot", "apartments",
        "makan", "ghar", "zameen", "plots", "kiraya"
    ],
    "health": [
        "health", "supplement", "vitamins", "skincare", "fitness", "organic",
        "sehat", "dawa", "ilaj", "desi jhari booti", "wazan"
    ],
    "education": [
        "education", "online course", "university", "academy", "admissions", "training",
        "taleem", "seekhain", "freelancing course", "huner"
    ],
    "general": [
        "sale", "offer", "discount", "shopping", "deals",
        "bachat", "sasta", "muft delivery", "fauri rabta", "chhoot"
    ],
}


def _load_mock(industry: Optional[str] = None) -> List[RawAdRecord]:
    """Load mock ad data from local JSON file and optionally filter by industry."""
    if not MOCK_DATA_PATH.exists():
        logger.error(f"Mock data file not found at: {MOCK_DATA_PATH}")
        return []

    try:
        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        records = [RawAdRecord(**item) for item in raw_data]

        if industry and industry.strip().lower() not in ["general", "all"]:
            filtered = [
                r for r in records
                if r.industry.strip().lower() == industry.strip().lower()
            ]
            if filtered:
                return filtered

        return records
    except Exception as e:
        logger.error(f"Error loading mock ads: {e}")
        return []


def _fetch_live(industry: str) -> List[RawAdRecord]:
    """Fetch live ads from Meta Graph API v19.0 ads_archive endpoint for Pakistan."""
    if not settings.META_API_TOKEN:
        logger.warning("META_API_TOKEN is not configured. Cannot fetch live ads.")
        return []

    normalized_key = industry.strip().lower().replace(" ", "_") if industry else "general"
    terms = INDUSTRY_SEARCH_TERMS.get(normalized_key, INDUSTRY_SEARCH_TERMS["general"])

    records: List[RawAdRecord] = []
    seen_ad_ids = set()

    for term in terms[:3]:
        try:
            resp = requests.get(
                "https://graph.facebook.com/v19.0/ads_archive",
                params={
                    "access_token": settings.META_API_TOKEN,
                    "ad_reached_countries": json.dumps(["PK"]),
                    "search_terms": term,
                    "ad_type": "ALL",
                    "limit": 25,
                    "fields": "id,page_name,ad_creative_bodies",
                },
                timeout=12,
            )
            resp.raise_for_status()

            payload = resp.json()
            ad_items = payload.get("data", [])

            for ad in ad_items:
                ad_id = str(ad.get("id", "")).strip()
                if not ad_id or ad_id in seen_ad_ids:
                    continue

                bodies = ad.get("ad_creative_bodies", [])
                if not bodies or not isinstance(bodies, list):
                    continue

                copy = bodies[0]
                if not copy or not isinstance(copy, str):
                    continue

                # Skip any ad where the body contains the word "removed"
                if "removed" in copy.lower():
                    continue

                seen_ad_ids.add(ad_id)
                records.append(
                    RawAdRecord(
                        ad_id=ad_id,
                        page_name=ad.get("page_name", "Unknown"),
                        ad_copy=copy,
                        industry=industry if industry else "general",
                        source_type="live_api",
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to fetch live ads for term '{term}': {e}")
            continue

    return records


def fetch_ads(industry: Optional[str] = "general", use_mock: Optional[bool] = None) -> List[RawAdRecord]:
    """Main entry point to fetch ads, routing to live API or local mock dataset."""
    should_mock = settings.USE_MOCK_DATA if use_mock is None else use_mock
    target_industry = industry or "general"

    if should_mock:
        return _load_mock(industry)

    records = _fetch_live(target_industry)

    if not records:
        logger.warning("Live API returned 0 records — falling back to mock.")
        return _load_mock(industry)

    return records