import re
from typing import List, Literal
from src.core.schemas import RawAdRecord, HookItem, HookAnalysisReport

# Common Roman-Urdu markers
ROMAN_URDU_WORDS = {
    "karein", "karo", "hai", "hain", "apna", "apni", "aap", "bhi", "yeh", "woh", 
    "ke", "ki", "ka", "ko", "se", "par", "mein", "fauri", "bachat", "asli", 
    "muft", "sasta", "behtareen", "rabta", "mangwayen", "dastiyab"
}

def detect_language(text: str) -> Literal["English", "Urdu", "Roman-Urdu", "Mixed"]:
    # Check for Urdu (Arabic/Nastaliq script range)
    has_arabic_script = bool(re.search(r"[\u0600-\u06FF]", text))
    
    # Tokenize lowercase words for Roman-Urdu check
    words = re.findall(r"\b[a-z]+\b", text.lower())
    if not words:
        return "Urdu" if has_arabic_script else "English"
        
    roman_count = sum(1 for w in words if w in ROMAN_URDU_WORDS)
    roman_ratio = roman_count / max(len(words), 1)
    
    if has_arabic_script and roman_count > 0:
        return "Mixed"
    if has_arabic_script:
        return "Urdu"
    if roman_ratio >= 0.08:
        return "Roman-Urdu"
    return "English"

def extract_raw_hook(text: str) -> str:
    """Extracts the first 1-2 sentences as the hook."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    first_block = lines[0]
    sentences = re.split(r"(?<=[.!?؟])\s+", first_block)
    return " ".join(sentences[:2]) if len(sentences) > 1 else first_block

def classify_single_hook(hook_text: str) -> Literal[
    "Problem-Agitation", 
    "Direct Offer / Discount", 
    "Social Proof / Trust", 
    "Curiosity / Question", 
    "Urgency / FOMO"
]:
    t = hook_text.lower()
    
    # 1. Curiosity / Question
    if "?" in hook_text or "؟" in hook_text or re.search(r"\b(kya aap|are you|looking for|want to)\b", t):
        return "Curiosity / Question"
        
    # 2. Urgency / FOMO
    if re.search(r"\b(fauri|jaldi|limited stock|ending soon|aaj hi|last chance|hurry)\b", t):
        return "Urgency / FOMO"
        
    # 3. Direct Offer / Discount
    if re.search(r"\b(flat|\d+%\s*off|sale|discount|free delivery|chhoot|rs\.?\s?\d+)\b", t):
        return "Direct Offer / Discount"
        
    # 4. Social Proof / Trust
    if re.search(r"\b(\d+[\d,]*\+?\s*(?:happy\s+|satisfied\s+)?(customers|students|reviews|clients|users|buyers|families|orders)|trust|trusted|authentic|asli|guarantee|verified)\b", t):
        return "Social Proof / Trust"
        
    # 5. Default heuristic: Problem-Agitation
    return "Problem-Agitation"

def analyze_hooks(ads: List[RawAdRecord]) -> HookAnalysisReport:
    items: List[HookItem] = []
    
    for ad in ads:
        hook_text = extract_raw_hook(ad.ad_copy)
        lang = detect_language(ad.ad_copy)
        hook_type = classify_single_hook(hook_text)
        
        items.append(
            HookItem(
                ad_id=ad.ad_id,
                page_name=ad.page_name,
                raw_hook=hook_text,
                hook_type=hook_type,
                language=lang
            )
        )
        
    total = len(items)
    if total == 0:
        return HookAnalysisReport(
            total_hooks_analyzed=0,
            dominant_hook_type="None",
            dominant_language="None",
            items=[]
        )
        
    type_counts = {}
    lang_counts = {}
    for item in items:
        type_counts[item.hook_type] = type_counts.get(item.hook_type, 0) + 1
        lang_counts[item.language] = lang_counts.get(item.language, 0) + 1
        
    dominant_type = max(type_counts, key=type_counts.get) if type_counts else "None"
    dominant_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "None"
    
    return HookAnalysisReport(
        total_hooks_analyzed=total,
        dominant_hook_type=dominant_type,
        dominant_language=dominant_lang,
        items=items
    )
