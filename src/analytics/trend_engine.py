"""Trend analytics engine for AdLens PK.

Computes market velocity, emerging hooks, and brand momentum from the
stored ad dataset.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.classifier import classify_single_hook, extract_raw_hook
from src.db.repository import get_all_ads, get_trend_data


def _get_industry(ad: Any) -> str:
    """Extract industry from RawAdRecord or dict."""
    if isinstance(ad, dict):
        return str(ad.get("industry", "general")).lower().strip() or "general"
    return str(getattr(ad, "industry", "general")).lower().strip() or "general"


def _parse_date(date_value: Any) -> Optional[datetime]:
    """Parse a date string or datetime object into a datetime."""
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value
    if isinstance(date_value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_value.split("Z")[0], fmt)
            except ValueError:
                continue
    return None


def _week_key(dt: datetime) -> str:
    """ISO calendar week key, e.g. '2026-W35'."""
    return dt.strftime("%Y-W%W")


def compute_trend_velocity(ads_by_date: Dict[str, List[Any]]) -> Dict[str, Any]:
    """
    Compute week-over-week ad-volume change per industry.

    Args:
        ads_by_date: Mapping of {date_str: list of RawAdRecord or dict}.

    Returns:
        Dict with rising_industries, declining_industries, stable_industries,
        and velocity_score (0-100).
    """
    # Aggregate counts per (week, industry)
    weekly_industry_counts: Dict[str, Counter] = defaultdict(Counter)
    total_per_week: Counter = Counter()

    for date_str, ads in ads_by_date.items():
        dt = _parse_date(date_str)
        if dt is None:
            continue
        week = _week_key(dt)
        for ad in ads:
            industry = _get_industry(ad)
            weekly_industry_counts[week][industry] += 1
            total_per_week[week] += 1

    sorted_weeks = sorted(weekly_industry_counts.keys())
    if len(sorted_weeks) < 2:
        # Not enough history for WoW; return flat result based on totals.
        totals = Counter()
        for counts in weekly_industry_counts.values():
            totals.update(counts)
        all_industries = [
            {"industry": ind, "growth_pct": 0.0} for ind, _ in totals.most_common()
        ]
        total_ads = sum(total_per_week.values())
        velocity_score = min(100.0, max(0.0, total_ads / 10.0))
        return {
            "rising_industries": all_industries,
            "declining_industries": [],
            "stable_industries": [],
            "velocity_score": round(velocity_score, 2),
        }

    current_week = sorted_weeks[-1]
    previous_week = sorted_weeks[-2]

    current_counts = weekly_industry_counts[current_week]
    previous_counts = weekly_industry_counts[previous_week]

    all_industries = set(current_counts.keys()) | set(previous_counts.keys())

    rising: List[Dict[str, Any]] = []
    declining: List[Dict[str, Any]] = []
    stable: List[Dict[str, Any]] = []

    for industry in sorted(all_industries):
        current = current_counts.get(industry, 0)
        previous = previous_counts.get(industry, 0)
        if previous == 0:
            growth_pct = 100.0 if current > 0 else 0.0
        else:
            growth_pct = round(((current - previous) / previous) * 100, 2)

        entry = {"industry": industry.title(), "growth_pct": growth_pct}
        if growth_pct > 5.0:
            rising.append(entry)
        elif growth_pct < -5.0:
            declining.append(entry)
        else:
            stable.append(entry)

    # Sort by magnitude
    rising.sort(key=lambda x: x["growth_pct"], reverse=True)
    declining.sort(key=lambda x: x["growth_pct"])
    stable.sort(key=lambda x: abs(x["growth_pct"]))

    # Velocity score: blend total volume growth with recent absolute volume
    prev_total = total_per_week[previous_week]
    curr_total = total_per_week[current_week]
    if prev_total == 0:
        growth_component = 100.0 if curr_total > 0 else 0.0
    else:
        growth_component = ((curr_total - prev_total) / prev_total) * 100
    growth_component = max(-100.0, min(100.0, growth_component))

    # Normalize to 0-100 (50 = flat, 100 = doubling, 0 = halving or worse)
    velocity_score = 50.0 + (growth_component / 2.0)
    velocity_score = max(0.0, min(100.0, velocity_score))

    return {
        "rising_industries": rising,
        "declining_industries": declining,
        "stable_industries": stable,
        "velocity_score": round(velocity_score, 2),
    }


def _classify_hooks(ads: List[Any]) -> Counter:
    """Classify hook types for a list of ads/dicts."""
    hooks = Counter()
    for ad in ads:
        if isinstance(ad, dict):
            text = str(ad.get("ad_copy", ""))
        else:
            text = str(getattr(ad, "ad_copy", ""))
        raw_hook = extract_raw_hook(text)
        hook_type = classify_single_hook(raw_hook)
        hooks[hook_type] += 1
    return hooks


def detect_emerging_hooks(current_ads: List[Any], historical_ads: List[Any]) -> List[Dict[str, Any]]:
    """
    Find hook types that appear more frequently in current_ads vs historical_ads.

    Returns list of dicts: hook_type, current_pct, historical_pct, change_pct.
    """
    current_hooks = _classify_hooks(current_ads)
    historical_hooks = _classify_hooks(historical_ads)

    current_total = sum(current_hooks.values())
    historical_total = sum(historical_hooks.values())

    if current_total == 0:
        return []

    all_types = set(current_hooks.keys()) | set(historical_hooks.keys())
    results: List[Dict[str, Any]] = []

    for hook_type in sorted(all_types):
        current_count = current_hooks.get(hook_type, 0)
        historical_count = historical_hooks.get(hook_type, 0)

        current_pct = round((current_count / current_total) * 100, 2)
        historical_pct = (
            round((historical_count / historical_total) * 100, 2)
            if historical_total > 0
            else 0.0
        )
        change_pct = round(current_pct - historical_pct, 2)

        results.append({
            "hook_type": hook_type,
            "current_pct": current_pct,
            "historical_pct": historical_pct,
            "change_pct": change_pct,
        })

    # Sort by biggest positive change first
    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results


def compute_brand_momentum(page_name: str) -> Dict[str, Any]:
    """
    Query the DB for a brand/page_name and compute momentum metrics.

    Returns:
        Dict with total_appearances, first_seen, last_seen, momentum.
        Momentum is "Growing" if last seen within 2 weeks,
        "Stable" if within 4 weeks, otherwise "Declining".
    """
    all_ads = get_all_ads()
    target = page_name.lower().strip()
    brand_ads = [
        ad
        for ad in all_ads
        if str(ad.get("page_name", "")).lower().strip() == target
    ]

    total_appearances = len(brand_ads)
    if total_appearances == 0:
        return {
            "page_name": page_name,
            "total_appearances": 0,
            "first_seen": None,
            "last_seen": None,
            "momentum": "Declining",
        }

    dates = []
    for ad in brand_ads:
        dt = _parse_date(ad.get("pulled_at"))
        if dt:
            dates.append(dt)

    if not dates:
        return {
            "page_name": page_name,
            "total_appearances": total_appearances,
            "first_seen": None,
            "last_seen": None,
            "momentum": "Stable",
        }

    dates.sort()
    first_seen = dates[0].isoformat()
    last_seen = dates[-1].isoformat()

    now = datetime.now()
    days_since_last = (now - dates[-1]).days

    if days_since_last <= 14:
        momentum = "Growing"
    elif days_since_last <= 28:
        momentum = "Stable"
    else:
        momentum = "Declining"

    return {
        "page_name": page_name,
        "total_appearances": total_appearances,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "momentum": momentum,
    }


def get_market_pulse() -> Dict[str, Any]:
    """
    Aggregate market pulse summary using DB data.

    Returns dict with velocity, emerging_hooks, total_ads, current_window_ads,
    historical_window_ads, and a sample brand momentum for the most active brand.
    """
    all_ads = get_all_ads()
    trend_rows = get_trend_data()

    now = datetime.now()
    cutoff = now - timedelta(days=7)

    current_ads: List[Dict[str, Any]] = []
    historical_ads: List[Dict[str, Any]] = []
    ads_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for ad in all_ads:
        dt = _parse_date(ad.get("pulled_at"))
        date_key = dt.strftime("%Y-%m-%d") if dt else "unknown"
        ads_by_date[date_key].append(ad)

        if dt and dt >= cutoff:
            current_ads.append(ad)
        else:
            historical_ads.append(ad)

    velocity = compute_trend_velocity(dict(ads_by_date))
    emerging_hooks = detect_emerging_hooks(current_ads, historical_ads)

    # Most active brand for sample momentum
    page_counts = Counter(str(ad.get("page_name", "Unknown")) for ad in all_ads)
    sample_brand = page_counts.most_common(1)[0][0] if page_counts else "Unknown"
    brand_momentum = compute_brand_momentum(sample_brand)

    return {
        "velocity": velocity,
        "emerging_hooks": emerging_hooks,
        "total_ads": len(all_ads),
        "current_window_ads": len(current_ads),
        "historical_window_ads": len(historical_ads),
        "sample_brand_momentum": brand_momentum,
        "trend_rows": trend_rows,
    }
