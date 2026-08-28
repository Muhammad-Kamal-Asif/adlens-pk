import json
import os
from typing import List, Optional
from src.core.schemas import RawAdRecord

def fetch_ads(industry: Optional[str] = None, use_mock: bool = True) -> List[RawAdRecord]:
    """
    Fetches raw ad records.
    Currently defaults to mock dataset to guarantee demo resilience.
    """
    if use_mock:
        return _load_mock_data(industry)
    
    # Placeholder for live Meta API Wrapper logic
    raise NotImplementedError("Live API integration pending phase 3.")

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
