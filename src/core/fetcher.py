import json
import logging
import os
from typing import List, Optional
import requests
from src.config.settings import settings
from src.core.schemas import RawAdRecord

logger = logging.getLogger(__name__)

API_ENDPOINT = "https://api.ad-wrapper.io/v1/search"


def fetch_ads(industry: Optional[str] = None, use_mock: bool = True) -> List[RawAdRecord]:
    """
    Fetches raw ad records.
    If use_mock=True, loads from the local curated mock dataset.
    Otherwise, executes a live API request to the Meta Ad Library wrapper,
    falling back gracefully to mock data on any network or API error.
    """
    if use_mock:
        return _load_mock_data(industry)
    
    return _fetch_from_api(industry)


def _fetch_from_api(industry: Optional[str] = None) -> List[RawAdRecord]:
    """
    Queries live third-party Meta Ad Library API endpoint with authorization,
    handling timeouts, network errors, and HTTP status errors gracefully.
    """
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AdLens-PK/1.0",
    }
    if settings.META_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.META_API_TOKEN}"

    params = {"country": "PK"}
    if industry:
        params["industry"] = industry

    try:
        response = requests.get(
            API_ENDPOINT,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        # Support direct list or nested data/ads structure
        items = data if isinstance(data, list) else data.get("data", data.get("ads", []))
        
        records = []
        for item in items:
            if isinstance(item, dict):
                item.setdefault("source_type", "live_api")
                records.append(RawAdRecord(**item))
                
        return records if records else _load_mock_data(industry)

    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning("Live API fetch failed (%s); falling back to mock dataset.", e)
        return _load_mock_data(industry)
    except Exception as e:
        logger.error("Unexpected error during live API fetch (%s); falling back to mock dataset.", e)
        return _load_mock_data(industry)


def _load_mock_data(industry_filter: Optional[str] = None) -> List[RawAdRecord]:
    """Loads and parses the curated fallback dataset."""
    file_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock_ads.json")
    
    if not os.path.exists(file_path):
        return []
        
    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    records = [RawAdRecord(**item) for item in raw_data]
    
    if industry_filter:
        records = [r for r in records if r.industry.lower() == industry_filter.lower()]
        
    return records
