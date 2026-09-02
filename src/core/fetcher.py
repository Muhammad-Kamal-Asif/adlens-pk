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
        "sale", "dress", "shirt", "clothing", "pk fashion",
        "lawn", "kapray", "kurti", "unstitched"
    ],
    "food": [
        "food", "delivery", "restaurant", "khana", "biryani",
        "deals", "mithai", "fast food"
    ],
    "electronics": [
        "mobile", "phone", "laptop", "gadget", "tech",
        "smart watch", "accessories", "sasta mobile"
    ],
    "real_estate": [
        "property", "plot", "house", "apartment", "zameen",
        "makan", "ghar", "commercial plot"
    ],
    "health": [
        "health", "supplement", "skin", "cream", "fitness",
        "skincare", "sehat", "dawa", "organic"
    ],
    "education": [
        "education", "course", "academy", "taleem", "learn",
        "online course", "admission", "freelancing"
    ],
    "general": [
        "sale", "offer", "buy", "discount", "pk",
        "bachat", "sasta", "muft delivery", "deals"
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
    MAX_RECORDS = 50
    MAX_PAGES_PER_TERM = 3

    for term in terms:
        if len(records) >= MAX_RECORDS:
            break

        page_count = 0
        next_url = None

        while page_count < MAX_PAGES_PER_TERM and len(records) < MAX_RECORDS:
            page_count += 1
            try:
                if next_url:
                    resp = requests.get(next_url, timeout=12)
                else:
                    resp = requests.get(
                        "https://graph.facebook.com/v19.0/ads_archive",
                        params={
                            "access_token": settings.META_API_TOKEN,
                            "ad_reached_countries": json.dumps(["PK"]),
                            "search_terms": term,
                            "ad_type": "ALL",
                            "limit": 50,
                            "fields": "id,page_name,ad_creative_bodies",
                        },
                        timeout=12,
                    )
                resp.raise_for_status()

                payload = resp.json()
                ad_items = payload.get("data", [])

                for ad in ad_items:
                    if len(records) >= MAX_RECORDS:
                        break

                    ad_id = str(ad.get("id", "")).strip()
                    if not ad_id or ad_id in seen_ad_ids:
                        continue

                    bodies = ad.get("ad_creative_bodies", [])
                    if not bodies or not isinstance(bodies, list):
                        continue

                    copy = bodies[0]
                    if not copy or not isinstance(copy, str):
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

                # Pagination: fetch next page URL if available
                paging = payload.get("paging", {})
                next_url = paging.get("next")
                if not next_url:
                    break

            except requests.exceptions.RequestException as e:
                status = e.response.status_code if e.response is not None else "Connection Error"
                logger.warning(f"Failed for term '{term}' (page {page_count}): HTTP {status}")
                break
            except Exception:
                logger.warning(f"Failed for term '{term}' (page {page_count}): Unknown Error")
                break

    return records


def fetch_ads(industry: Optional[str] = "general", use_mock: Optional[bool] = None) -> List[RawAdRecord]:
    """Main entry point to fetch ads, routing to live API or local mock dataset."""
    from src.db.watchlist import check_and_update_watchlist

    should_mock = settings.USE_MOCK_DATA if use_mock is None else use_mock
    target_industry = industry or "general"

    if should_mock:
        records = _load_mock(industry)
    else:
        records = _fetch_live(target_industry)
        if not records:
            logger.warning("Live API returned 0 records — falling back to mock.")
            records = _load_mock(industry)

    if records:
        check_and_update_watchlist(records)

    return records