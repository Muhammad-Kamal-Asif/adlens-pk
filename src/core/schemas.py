from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class RawAdRecord(BaseModel):
    ad_id: str
    page_name: str
    ad_copy: str
    media_type: Literal["image", "video", "carousel", "unknown"] = "image"
    cta_raw: Optional[str] = "LEARN_MORE"
    days_active: int = 1
    industry: str
    source_type: Literal["curated_seed", "live_api"] = "curated_seed"

class AdOfferDetails(BaseModel):
    ad_id: str
    page_name: str
    price_mentioned: Optional[str] = None
    discount_percentage: Optional[int] = None
    has_cash_on_delivery: bool = False
    free_delivery_mentioned: bool = False
    primary_cta: Literal["Shop Now", "Send WhatsApp Message", "Learn More", "Order Now", "Call Now", "Other"]
    detected_intent_words: List[str] = Field(default_factory=list)

class OfferMatrixSummary(BaseModel):
    total_ads_evaluated: int
    cod_prevalence_pct: float
    free_shipping_prevalence_pct: float
    most_common_cta: str
    price_ranges_detected: List[str]
    records: List[AdOfferDetails]

class HookItem(BaseModel):
    ad_id: str
    page_name: str
    raw_hook: str
    hook_type: Literal[
        "Problem-Agitation", 
        "Direct Offer / Discount", 
        "Social Proof / Trust", 
        "Curiosity / Question", 
        "Urgency / FOMO"
    ]
    language: Literal["English", "Urdu", "Roman-Urdu", "Mixed"]

class HookAnalysisReport(BaseModel):
    total_hooks_analyzed: int
    dominant_hook_type: str
    dominant_language: str
    items: List[HookItem]

class TacticalCreativeBrief(BaseModel):
    target_niche: str
    market_whitespace: str
    recommended_angle: str
    suggested_hooks: List[str]
    recommended_offer_structure: str
