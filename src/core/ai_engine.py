import json
import os
from typing import Optional
from src.config.settings import settings
from src.core.schemas import HookAnalysisReport, OfferMatrixSummary, TacticalCreativeBrief

def generate_tactical_brief(
    niche: str, 
    hook_report: HookAnalysisReport, 
    offer_matrix: OfferMatrixSummary
) -> TacticalCreativeBrief:
    """
    Synthesizes competitive data into an actionable creative brief.
    Uses Google Gemini if API key is present; otherwise falls back to a deterministic generator.
    """
    if settings.GEMINI_API_KEY:
        try:
            return _generate_with_gemini(niche, hook_report, offer_matrix)
        except Exception:
            # Fall back seamlessly if API call fails
            pass
            
    return _generate_fallback_brief(niche, hook_report, offer_matrix)

def _generate_with_gemini(
    niche: str, 
    hook_report: HookAnalysisReport, 
    offer_matrix: OfferMatrixSummary
) -> TacticalCreativeBrief:
    import google.generativeai as genai
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
You are an expert performance marketing strategist specializing in the Pakistani digital advertising ecosystem.
Analyze the following competitive data for the '{niche}' industry and produce a tactical campaign strategy brief.

Data Summary:
- Total Ads Evaluated: {hook_report.total_hooks_analyzed}
- Dominant Hook Type: {hook_report.dominant_hook_type}
- Dominant Copy Language: {hook_report.dominant_language}
- COD Prevalence: {offer_matrix.cod_prevalence_pct}%
- Free Shipping Prevalence: {offer_matrix.free_shipping_prevalence_pct}%
- Primary CTA Used: {offer_matrix.most_common_cta}

Respond strictly with valid JSON matching this schema:
{{
  "target_niche": "{niche}",
  "market_whitespace": "Identified creative gap in Pakistani market",
  "recommended_angle": "Recommended psychological creative angle",
  "suggested_hooks": [
    "Hook 1 in Roman-Urdu / English",
    "Hook 2 in Roman-Urdu / English",
    "Hook 3 in Roman-Urdu / English"
  ],
  "recommended_offer_structure": "Recommended pricing, COD, and CTA structure"
}}
"""
    response = model.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    data = json.loads(response.text)
    return TacticalCreativeBrief(**data)

def _generate_fallback_brief(
    niche: str, 
    hook_report: HookAnalysisReport, 
    offer_matrix: OfferMatrixSummary
) -> TacticalCreativeBrief:
    """Deterministic fallback strategy brief to guarantee reliable offline demos."""
    return TacticalCreativeBrief(
        target_niche=niche,
        market_whitespace=(
            f"Competitors heavily lean on '{hook_report.dominant_hook_type}' in {hook_report.dominant_language}. "
            "There is an untapped whitespace in authentic Roman-Urdu problem-agitation and UGC social proof formats."
        ),
        recommended_angle="Problem-Agitation with Direct Roman-Urdu Vernacular Triggers",
        suggested_hooks=[
            f"Kya aap bhi {niche} mein bar bar nuqsan utha rahe hain? Fauri hal dekhein.",
            f"Pakistani market ka no.1 verified {niche} solution — ab COD dastiyab hai.",
            f"Limited Stock: Flat discount aur free delivery ke sath aaj hi order karein!"
        ],
        recommended_offer_structure=(
            f"Pair a risk-reversal offer (Cash on Delivery enabled, standard threshold) "
            f"with a direct '{offer_matrix.most_common_cta}' CTA to minimize conversion friction."
        )
    )
