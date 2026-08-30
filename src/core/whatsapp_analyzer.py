import re
import logging
from typing import List, Dict, Any, Optional

from src.core.schemas import RawAdRecord

logger = logging.getLogger(__name__)

# Regular expressions for detecting WhatsApp mentions and Pakistani mobile numbers
_WHATSAPP_PATTERN = re.compile(
    r"\b(whatsapp|whats\s*app|wa\.me|watsapp|whatapp|whtsapp|wats\s*app)\b",
    re.IGNORECASE,
)

_PK_PHONE_PATTERN = re.compile(
    r"(?:\+92|0092|92|0)[\s\-]?(3\d{2})[\s\-]?(\d{3})[\s\-]?(\d{4})|"
    r"(?:\+92|0092|92|0)[\s\-]?(3\d{2})[\s\-]?(\d{7})"
)


def detect_whatsapp_cta(ad_copy: str) -> Dict[str, Any]:
    """
    Detects WhatsApp mentions, phone numbers, and surrounding CTA phrases in ad copy.

    Returns:
        dict: {
            "has_whatsapp": bool,
            "whatsapp_number": str or None,
            "cta_phrase": str
        }
    """
    if not ad_copy or not isinstance(ad_copy, str):
        return {
            "has_whatsapp": False,
            "whatsapp_number": None,
            "cta_phrase": "",
        }

    has_whatsapp_mention = bool(_WHATSAPP_PATTERN.search(ad_copy))

    # Search for Pakistani mobile phone number
    phone_match = _PK_PHONE_PATTERN.search(ad_copy)
    whatsapp_number = None

    if phone_match:
        raw_num = phone_match.group(0).strip()
        # Clean and standardize number format: +92 3XX XXXXXXX or 03XX-XXXXXXX
        digits = re.sub(r"\D", "", raw_num)
        if digits.startswith("923") and len(digits) == 12:
            whatsapp_number = f"+92 {digits[2:5]} {digits[5:]}"
        elif digits.startswith("03") and len(digits) == 11:
            whatsapp_number = f"{digits[:4]}-{digits[4:]}"
        elif digits.startswith("3") and len(digits) == 10:
            whatsapp_number = f"+92 {digits[:3]} {digits[3:]}"
        else:
            whatsapp_number = raw_num

    # Extract surrounding CTA phrase (sentence or clause)
    cta_phrase = ""
    if has_whatsapp_mention or phone_match:
        sentences = re.split(r"[.\n!?|•]", ad_copy)
        for s in sentences:
            s_clean = s.strip()
            if _WHATSAPP_PATTERN.search(s_clean) or (phone_match and phone_match.group(0) in s_clean):
                cta_phrase = s_clean
                break
        if not cta_phrase:
            # Fallback to a window around match
            match = _WHATSAPP_PATTERN.search(ad_copy) or phone_match
            if match:
                start = max(0, match.start() - 30)
                end = min(len(ad_copy), match.end() + 30)
                cta_phrase = ad_copy[start:end].strip()

    # Consider ad as having WhatsApp if mention exists or phone number found in commercial context
    has_whatsapp = has_whatsapp_mention or (phone_match is not None and len(cta_phrase) > 0)

    return {
        "has_whatsapp": has_whatsapp,
        "whatsapp_number": whatsapp_number,
        "cta_phrase": cta_phrase,
    }


def analyze_whatsapp_patterns(ads: List[Any]) -> Dict[str, Any]:
    """
    Analyzes WhatsApp adoption patterns, longevity, and industry distributions across ads.

    Returns:
        dict: {
            "whatsapp_adoption_pct": float,
            "whatsapp_vs_website_ratio": str,
            "avg_days_active_whatsapp": float,
            "avg_days_active_non_whatsapp": float,
            "top_whatsapp_industries": list of dicts,
            "sample_whatsapp_ads": list of dicts,
            "total_whatsapp_ads": int,
            "total_ads_evaluated": int
        }
    """
    if not ads:
        return {
            "whatsapp_adoption_pct": 0.0,
            "whatsapp_vs_website_ratio": "0:0",
            "avg_days_active_whatsapp": 0.0,
            "avg_days_active_non_whatsapp": 0.0,
            "top_whatsapp_industries": [],
            "sample_whatsapp_ads": [],
            "total_whatsapp_ads": 0,
            "total_ads_evaluated": 0,
        }

    whatsapp_ads = []
    non_whatsapp_ads = []
    industry_counts: Dict[str, int] = {}
    sample_ads: List[Dict[str, Any]] = []

    for item in ads:
        # Support RawAdRecord object or dict
        if isinstance(item, dict):
            ad_copy = item.get("ad_copy", "")
            page_name = item.get("page_name", "Unknown Brand")
            industry = item.get("industry", "General")
            days_active = int(item.get("days_active", 1) or 1)
            cta_raw = item.get("cta_raw", "")
        else:
            ad_copy = getattr(item, "ad_copy", "")
            page_name = getattr(item, "page_name", "Unknown Brand")
            industry = getattr(item, "industry", "General")
            days_active = int(getattr(item, "days_active", 1) or 1)
            cta_raw = getattr(item, "cta_raw", "")

        wa_data = detect_whatsapp_cta(ad_copy)
        is_wa_cta = cta_raw and ("WHATSAPP" in str(cta_raw).upper() or "WA.ME" in str(cta_raw).lower())

        if wa_data["has_whatsapp"] or is_wa_cta:
            whatsapp_ads.append(days_active)
            ind_clean = str(industry).strip().title() if industry else "General"
            industry_counts[ind_clean] = industry_counts.get(ind_clean, 0) + 1

            if len(sample_ads) < 5:
                sample_ads.append({
                    "page_name": page_name,
                    "whatsapp_number": wa_data["whatsapp_number"] or "Direct WA Link",
                    "days_active": days_active,
                    "ad_copy": ad_copy[:80] + ("..." if len(ad_copy) > 80 else ""),
                    "industry": ind_clean,
                    "cta_phrase": wa_data["cta_phrase"],
                })
        else:
            non_whatsapp_ads.append(days_active)

    total_evaluated = len(ads)
    total_wa = len(whatsapp_ads)
    total_non_wa = len(non_whatsapp_ads)

    adoption_pct = round((total_wa / total_evaluated) * 100.0, 1) if total_evaluated > 0 else 0.0
    avg_days_wa = round(sum(whatsapp_ads) / total_wa, 1) if total_wa > 0 else 0.0
    avg_days_non_wa = round(sum(non_whatsapp_ads) / total_non_wa, 1) if total_non_wa > 0 else 0.0

    ratio_str = f"{total_wa}:{total_non_wa}"

    top_industries = [
        {"industry": ind, "count": cnt, "adoption_pct": round((cnt / max(1, total_wa)) * 100.0, 1)}
        for ind, cnt in sorted(industry_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "whatsapp_adoption_pct": adoption_pct,
        "whatsapp_vs_website_ratio": ratio_str,
        "avg_days_active_whatsapp": avg_days_wa,
        "avg_days_active_non_whatsapp": avg_days_non_wa,
        "top_whatsapp_industries": top_industries,
        "sample_whatsapp_ads": sample_ads,
        "total_whatsapp_ads": total_wa,
        "total_ads_evaluated": total_evaluated,
    }


def get_whatsapp_insight(pct: float) -> str:
    """
    Returns a strategic executive insight string based on the WhatsApp adoption rate.
    """
    if pct >= 50.0:
        return (
            f"WhatsApp-Dominant Direct Response ({pct:.1f}% Adoption): Direct conversational "
            "commerce overwhelmingly powers this vertical. Pakistani consumers strongly prefer "
            "personal negotiation, manual order confirmation, and instant WhatsApp support over automated website checkouts."
        )
    elif pct >= 30.0:
        return (
            f"Hybrid Funnel Equilibrium ({pct:.1f}% Adoption): Significant split between click-to-WhatsApp "
            "inquiries and e-commerce store checkouts. Advertisers running WhatsApp funnels typically experience "
            "higher lead conversion on COD orders by eliminating checkout friction."
        )
    elif pct >= 15.0:
        return (
            f"Emerging High-Touch Channel ({pct:.1f}% Adoption): Website checkouts predominate, but scaling "
            "brands leverage WhatsApp for high-ticket consultations, COD verification, and direct customer re-engagement."
        )
    else:
        return (
            f"Website-First Funnel ({pct:.1f}% Adoption): Automated online checkouts lead this category. "
            "Introducing click-to-WhatsApp campaigns for abandoned inquiries and customized packages presents "
            "an immediate untapped whitespace."
        )
