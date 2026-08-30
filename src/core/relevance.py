import logging
import re
from typing import List
from src.core.schemas import RawAdRecord

logger = logging.getLogger(__name__)

# Dictionary mapping each industry to 20+ relevant terms
INDUSTRY_KEYWORDS = {
    "fashion": [
        "sale", "dress", "shirt", "clothing", "pk fashion", "lawn", "kapray", "kurti",
        "unstitched", "stitched", "pret", "collection", "outfit", "wardrobe", "apparel",
        "boutique", "designer", "fabric", "embroidered", "chiffon", "summer", "winter", "style"
    ],
    "food": [
        "food", "delivery", "restaurant", "khana", "biryani", "deals", "mithai", "fast food",
        "pizza", "burger", "taste", "delicious", "menu", "dine", "takeaway", "spicy",
        "sweet", "meal", "combo", "discount", "cravings", "chef", "cafe"
    ],
    "electronics": [
        "mobile", "phone", "laptop", "gadget", "tech", "smart watch", "accessories",
        "sasta mobile", "earbuds", "headphones", "charger", "power bank", "warranty",
        "camera", "screen", "battery", "gaming", "device", "bluetooth", "wireless",
        "discount", "sale"
    ],
    "real_estate": [
        "property", "plot", "house", "apartment", "zameen", "makan", "ghar", "commercial",
        "residential", "investment", "installment", "society", "bahria", "dha", "location",
        "possession", "real estate", "rent", "buy", "sell", "development", "project"
    ],
    "health": [
        "health", "supplement", "skin", "cream", "fitness", "skincare", "sehat", "dawa",
        "organic", "vitamin", "gym", "weight loss", "protein", "natural", "doctor",
        "clinic", "treatment", "hair", "glow", "care", "beauty", "medicine", "wellness"
    ],
    "education": [
        "education", "course", "academy", "taleem", "learn", "online", "admission",
        "freelancing", "degree", "university", "school", "college", "institute",
        "skills", "training", "diploma", "certification", "study", "student", "class",
        "english", "computer", "it"
    ],
    "general": [
        "sale", "offer", "buy", "discount", "pk", "bachat", "sasta", "muft", "deals",
        "limited", "time", "best", "price", "quality", "free", "shipping", "delivery",
        "order", "now", "shop", "store", "save", "mega"
    ]
}

def score_ad_relevance(ad: RawAdRecord, industry: str) -> float:
    """Returns a score 0.0 to 1.0 based on keyword matches in ad_copy."""
    industry_key = industry.strip().lower().replace(" ", "_") if industry else "general"
    keywords = INDUSTRY_KEYWORDS.get(industry_key, INDUSTRY_KEYWORDS["general"])
    
    if not keywords:
        return 0.0
        
    ad_copy_lower = (ad.ad_copy or "").lower()
    
    matches = 0
    for kw in keywords:
        # Use simple string inclusion or regex word boundary
        if re.search(rf'\b{re.escape(kw.lower())}\b', ad_copy_lower):
            matches += 1
            
    # Score = (matching keywords found) / (total keywords for industry)
    return float(matches) / len(keywords)

def filter_by_relevance(ads: List[RawAdRecord], industry: str, threshold: float = 0.05) -> List[RawAdRecord]:
    """Filters ads by relevance score. If filtering leaves fewer than 10, returns top 20 by score."""
    if not ads:
        return []
        
    scored_ads = [(ad, score_ad_relevance(ad, industry)) for ad in ads]
    
    # Sort descending by score
    scored_ads.sort(key=lambda x: x[1], reverse=True)
    
    filtered_ads = [ad for ad, score in scored_ads if score >= threshold]
    
    if len(filtered_ads) < 10:
        logger.info(f"Relevance filter left only {len(filtered_ads)} ads. Falling back to top 20.")
        return [ad for ad, score in scored_ads[:20]]
        
    return filtered_ads
