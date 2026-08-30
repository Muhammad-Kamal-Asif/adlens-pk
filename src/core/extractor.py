import re
from typing import List
from src.core.schemas import RawAdRecord, AdOfferDetails, OfferMatrixSummary

# Local Commercial Triggers
INTENT_WORDS = [
    "fauri", "bachat", "asli", "jaldi", "sale",
    "chhoot", "limited stock", "rabta", "discount"
]


def get_survivor_ads(ads: List[RawAdRecord], min_days: int = 30) -> List[RawAdRecord]:
    """
    Returns ads that have been running for at least min_days.
    Useful for identifying durable, long-running creative winners.
    """
    return [ad for ad in ads if getattr(ad, "days_active", 0) >= min_days]


def extract_offer_details(ad: RawAdRecord) -> AdOfferDetails:
    text = ad.ad_copy.lower()
    
    # Extract Price (e.g., Rs. 1499, PKR 2000)
    price_match = re.search(r"(?:rs\.?|pkr)\s?([0-9,]+)", text)
    price_mentioned = f"Rs. {price_match.group(1)}" if price_match else None
    
    # Extract Discount Percentage
    discount_match = re.search(r"(\d+)%\s*(?:off|chhoot|discount)", text)
    discount_pct = int(discount_match.group(1)) if discount_match else None
    
    # Evaluate boolean commercial terms
    has_cod = bool(re.search(r"\b(cash on delivery|cod|payment on delivery)\b", text))
    free_delivery = bool(re.search(r"\b(free delivery|free shipping|muft delivery|zero delivery)\b", text))
    
    # CTA Normalization
    raw_cta = ad.cta_raw.upper() if ad.cta_raw else ""
    if "WHATSAPP" in raw_cta or "MESSAGE" in raw_cta:
        primary_cta = "Send WhatsApp Message"
    elif "SHOP" in raw_cta or "BUY" in raw_cta:
        primary_cta = "Shop Now"
    elif "ORDER" in raw_cta:
        primary_cta = "Order Now"
    elif "CALL" in raw_cta:
        primary_cta = "Call Now"
    elif "LEARN" in raw_cta:
        primary_cta = "Learn More"
    else:
        primary_cta = "Other"
        
    # Extract Vernacular Intent Triggers
    detected_words = [word for word in INTENT_WORDS if word in text]
    
    return AdOfferDetails(
        ad_id=ad.ad_id,
        page_name=ad.page_name,
        price_mentioned=price_mentioned,
        discount_percentage=discount_pct,
        has_cash_on_delivery=has_cod,
        free_delivery_mentioned=free_delivery,
        primary_cta=primary_cta,
        detected_intent_words=detected_words
    )

def build_offer_matrix(ads: List[RawAdRecord]) -> OfferMatrixSummary:
    records = [extract_offer_details(ad) for ad in ads]
    total = len(records)
    
    if total == 0:
        return OfferMatrixSummary(
            total_ads_evaluated=0, cod_prevalence_pct=0.0,
            free_shipping_prevalence_pct=0.0, most_common_cta="None",
            price_ranges_detected=[], records=[]
        )
        
    cod_count = sum(1 for r in records if r.has_cash_on_delivery)
    free_ship_count = sum(1 for r in records if r.free_delivery_mentioned)
    
    # Find most common CTA safely
    cta_counts = {}
    for r in records:
        cta_counts[r.primary_cta] = cta_counts.get(r.primary_cta, 0) + 1
    most_common_cta = max(cta_counts, key=cta_counts.get) if cta_counts else "None"
    
    # Collect unique price brackets
    prices = list({r.price_mentioned for r in records if r.price_mentioned})
    
    return OfferMatrixSummary(
        total_ads_evaluated=total,
        cod_prevalence_pct=round((cod_count / total) * 100, 1),
        free_shipping_prevalence_pct=round((free_ship_count / total) * 100, 1),
        most_common_cta=most_common_cta,
        price_ranges_detected=prices,
        records=records
    )

def compute_competitive_density(ads: List[RawAdRecord]) -> dict:
    if not ads:
        return {
            "unique_advertisers": 0,
            "avg_ads_per_brand": 0.0,
            "dominant_brand": "N/A",
            "top_5_brands": [],
        }

    brand_counts: dict = {}
    for ad in ads:
        brand_counts[ad.page_name] = brand_counts.get(ad.page_name, 0) + 1

    unique_advertisers = len(brand_counts)
    avg_ads_per_brand = round(len(ads) / unique_advertisers, 1)
    dominant_brand = max(brand_counts, key=brand_counts.get)
    top_5_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "unique_advertisers": unique_advertisers,
        "avg_ads_per_brand": avg_ads_per_brand,
        "dominant_brand": dominant_brand,
        "top_5_brands": [{"page_name": name, "count": count} for name, count in top_5_brands],
    }
