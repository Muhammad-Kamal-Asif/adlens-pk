"""
AdLens PK - Synthetic Demo Dataset Generator
Programmatically generates diverse Pakistani ad records using Google Gemini
(with automatic exponential backoff retry for rate limits & parse errors)
or high-fidelity local synthesis when offline/unauthenticated,
and appends validated records to src/data/mock_ads.json.
"""

import json
import logging
import os
import random
import re
import sys
import time
import uuid
from typing import List, Optional

# Force UTF-8 stdout if available
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pydantic import ValidationError
from src.config.settings import settings
from src.core.schemas import RawAdRecord

DATA_FILE_PATH = os.path.join(REPO_ROOT, "src", "data", "mock_ads.json")

BATCHES = [
    {
        "category": "Digital Marketing & Client Acquisition Agencies",
        "industry": "Marketing",
        "count": 15,
        "instructions": (
            "Focus on Pakistani B2B digital agencies, performance media buyers, "
            "and lead-generation consultants targeting local brand owners and real estate developers. "
            "Hooks should focus on ROAS guarantees, scaling ad spend, WhatsApp lead generation, and client acquisition."
        ),
    },
    {
        "category": "Technology Winter Bootcamps & EdTech",
        "industry": "EdTech",
        "count": 15,
        "instructions": (
            "Focus on Pakistani tech institutes offering Full-Stack Development, AI/GenAI cohorts, "
            "MERN stack, Flutter, and Amazon/Shopify freelancing bootcamps. "
            "Hooks should focus on high-paying remote US/UK jobs, freelancing dollar earnings, "
            "early-bird registration discounts (e.g., Rs. 1499 - Rs. 4999), and live mentorship."
        ),
    },
    {
        "category": "Local D2C E-Commerce Brands",
        "industry": "E-Commerce",
        "count": 15,
        "instructions": (
            "Focus on Pakistani direct-to-consumer e-commerce brands: unstitched winter lawn/khaddar, "
            "organic skincare serums, handmade Peshawari chappals, leather wallets, and smart kitchen gadgets. "
            "Hooks must heavily feature Cash on Delivery (COD), mega bachat/sale discounts, "
            "free shipping thresholds (e.g. Orders over Rs. 2499), and 'fauri order karein'."
        ),
    },
]

# High-fidelity curated offline generation templates
CURATED_OFFLINE_TEMPLATES = {
    "Marketing": [
        ("ScaleFlow PK", "Kya aap apni e-commerce sales 3X scale karna chahte hain? Hamara proven scale blueprint ab live hai! 50+ local brands trust us. Fauri rabta karein WhatsApp par.", "video", "WHATSAPP_MESSAGE", 18),
        ("AdGrowth Lahore", "Stop wasting ad spend on unoptimized Meta campaigns. Hamari verified lead acquisition funnel se payein guaranteed ROAS. Call now for a free audit.", "image", "CALL_NOW", 12),
        ("ClientForge PK", "Real estate aur B2B brands ke liye verified lead-generation machine! Fauri rabta karein aur high-ticket buyers hasil karein.", "image", "SEND_MESSAGE", 9),
        ("ROAS Ninja Pakistan", "Kya aapke Facebook ads mehenga CPC de rahe hain? Humare performance marketing bundle se bachat karein aur sales barhayen.", "video", "LEARN_MORE", 24),
        ("Apex Agency Karachi", "پاکستان کے ای کامرس برانڈز کے لیے سب سے بڑا گروتھ ہب۔ ابھی رابطہ کریں اور اپنے کاروبار کو وسعت دیں۔", "carousel", "SEND_MESSAGE", 15),
        ("DigiScale Islamabad", "Generate 100+ qualified leads daily without burning cash! Flat 40% discount on first-month agency retainer.", "image", "LEARN_MORE", 6),
        ("ViralPulse Media", "Ab har product viral hoga! TikTok aur Meta Ads ki complete management. Fauri WhatsApp par message bhejein.", "video", "WHATSAPP_MESSAGE", 14),
        ("BrandBoost Pakistan", "E-commerce store start kiya hai lekin orders nahi aa rahe? Hamari proven growth strategy se 10X revenue achieve karein.", "image", "SHOP_NOW", 30),
        ("MediaCraft PK", "100% authentic performance marketing audits for fashion and retail brands. Limited spots available for this month!", "carousel", "LEARN_MORE", 11),
        ("AdVantage Digital", "Kya aap WhatsApp funnels se daily 50+ direct orders chahte hain? Free demo consultation book karein.", "video", "CALL_NOW", 8),
        ("ClickSprout PK", "Boost your Shopify store conversion rate today! Fauri rabta karein aur exclusive bachat offer unlock karein.", "image", "LEARN_MORE", 21),
        ("TargetGen Agency", "کامیاب ڈیجیٹل مارکیٹنگ کے لیے مستند حل۔ اپنے برانڈ کو پاکستان بھر میں مقبول بنائیں۔", "image", "SEND_MESSAGE", 16),
        ("FunnelLab PK", "Stop losing customers at checkout! Optimize your Pakistani COD funnel and reduce RTO by 35%. Learn more.", "video", "LEARN_MORE", 27),
        ("DirectLeads Pakistan", "High-converting B2B WhatsApp campaigns setup within 48 hours. Fauri rabta karein aur apna setup claim karein.", "carousel", "WHATSAPP_MESSAGE", 5),
        ("CreativeWave Studio", "Professional ad creatives and video hooks tailored for Pakistani audiences. Rs. 4999 starting package.", "image", "ORDER_NOW", 19),
    ],
    "EdTech": [
        ("CodeCamp Pakistan", "Master Python & Generative AI in 10 weeks with live industry mentorship. Registration fee sirf Rs. 1999! Limited seats available.", "video", "LEARN_MORE", 14),
        ("FreelancePro PK", "Freelancing se monthly $500-$1500 earn karna chahte hain? Join our Upwork & Fiverr Mastery batch. Fauri rabta karein!", "image", "WHATSAPP_MESSAGE", 22),
        ("SkillForge Islamabad", "MERN Stack Development Bootcamp: Zero se Hero banien. Flat 30% bachat discount for the first 30 students.", "carousel", "LEARN_MORE", 10),
        ("DevMasters Lahore", "Amazon Wholesale & Private Label Practical Masterclass. 1000+ graduates already earning. Rs. 2499 registration.", "video", "ORDER_NOW", 17),
        ("NextGen Coder", "آن لائن کوڈنگ اور ویب ڈویلپمنٹ سیکھیں۔ گھر بیٹھے ڈالرز کمائیں اور اپنا مستقبل سنواریں۔", "image", "LEARN_MORE", 25),
        ("UIUX Academy PK", "Become a certified Product Designer in 8 weeks! Figma mastery aur live client portfolio building.", "video", "LEARN_MORE", 8),
        ("ShopifyExperts PK", "E-commerce store banana aur scale karna seekhein. Fauri rabta karein aur flat 40% discount payein.", "carousel", "WHATSAPP_MESSAGE", 13),
        ("DataMinds Pakistan", "Data Science and Machine Learning bootcamp with guaranteed internship opportunities. Apply today!", "image", "LEARN_MORE", 31),
        ("FlutterDev Hub", "Build cross-platform mobile apps for iOS & Android. Early-bird price Rs. 2999 only. Limited stock.", "video", "ORDER_NOW", 7),
        ("CyberShield PK", "Ethical Hacking & Cyber Security professional training in Pakistan. Verified certificate included.", "image", "LEARN_MORE", 19),
        ("DigitalMarketer PK", "Performance marketing aur Meta ad buying seekhein practical live accounts ke sath. Call now to enroll.", "video", "CALL_NOW", 12),
        ("UrduTech Academy", "کمپیوٹر سائنس اور اے آئی کی جدید ترین تعلیم اردو زبان میں۔ ابھی رجسٹر کریں۔", "image", "LEARN_MORE", 15),
        ("EnglishPro Pakistan", "Fluent spoken English and business communication for remote jobs. Free demo class today!", "carousel", "WHATSAPP_MESSAGE", 6),
        ("GrowthInstitute PK", "High-income remote tech skills seekhein aur US clients ke sath kaam karein. Fauri rabta karein.", "video", "LEARN_MORE", 20),
        ("ContentCrafters PK", "Copywriting and SEO Masterclass: Write high-converting sales copies for global clients. Rs. 1499 only.", "image", "SHOP_NOW", 16),
    ],
    "E-Commerce": [
        ("Zeenat Fabrics PK", "Winter Khaddar Collection 2026 is LIVE! Pure fabric, gorgeous embroidery. Rs. 2499 with Free delivery across Pakistan & Cash on Delivery available.", "carousel", "SHOP_NOW", 28),
        ("Peshawar Kheri", "Authentic Handmade Traditional Peshawari Chappal in genuine leather. Cash on delivery dastiyab hai. Sirf Rs. 2999!", "image", "ORDER_NOW", 14),
        ("DermaGlow PK", "Say goodbye to dark spots with our Vitamin C Glow Serum! Flat 50% chhoot, fauri rabta karein COD dastiyab hai. Rs. 1299 only.", "video", "SHOP_NOW", 35),
        ("HomeEase Pakistan", "Smart vegetable cutter and multifunctional kitchen gadget. Mega Bachat sale: 40% off with Free shipping all over Pakistan.", "video", "ORDER_NOW", 9),
        ("Shahi Libas", "خالص لان اور کھدر کے پرنٹڈ سوٹ۔ پورے پاکستان میں کیش آن ڈلیوری اور مفت شپنگ دستیاب ہے۔", "carousel", "SHOP_NOW", 21),
        ("LeatherCraft PK", "Handcrafted premium leather wallet & belt gift set. Cash on delivery available. Fauri order karein!", "image", "ORDER_NOW", 16),
        ("NutriPure Pakistan", "100% Pure Organic Sidr Honey from Karak. Laboratory tested & authentic. Rs. 1850 with COD.", "image", "SHOP_NOW", 19),
        ("GlamourTouch PK", "Matte Long-Lasting Waterproof Lipsticks set of 6. Flat 35% discount aur free delivery on Rs. 2000+ orders.", "video", "SHOP_NOW", 11),
        ("TechBazaar Karachi", "Ultra-fast wireless power bank 20,000mAh with LED display. Cash on delivery available all cities.", "image", "ORDER_NOW", 24),
        ("ModestWear PK", "Premium Turkish Chiffon Hijabs bundle offer! 4 hijabs for Rs. 1999 with muft delivery all over Pakistan.", "carousel", "SHOP_NOW", 30),
        ("FitPulse Pakistan", "Smart fitness tracker with heart-rate & sleep monitor. Special Bachat discount: Rs. 2499 only.", "video", "ORDER_NOW", 8),
        ("BabyComfort PK", "Ultra-soft organic cotton baby rompers pack of 3. Cash on delivery dastiyab hai, fauri mangwayen.", "image", "SHOP_NOW", 15),
        ("AromaScents PK", "Long-lasting luxury Arabic oud & French perfumes. Buy 1 Get 1 Free with Cash on delivery.", "video", "ORDER_NOW", 18),
        ("RoyalFootwear PK", "Handmade leather loafers for men. Pure comfort, verified quality. Rs. 3499 with Free shipping.", "carousel", "SHOP_NOW", 22),
        ("CrispCook PK", "Non-stick granite cookware set with heat-resistant handles. Flat 45% off sale! Fauri order karein.", "image", "ORDER_NOW", 13),
    ],
}


def clean_json_response(raw_text: str) -> str:
    """Strips Markdown fences or formatting artifacts from LLM response."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return text.strip()


def generate_batch_with_retry(
    batch_info: dict,
    batch_index: int,
    model,
    max_retries: int = 5,
    initial_delay: float = 3.0,
) -> List[RawAdRecord]:
    """Generates a batch of ads using Gemini with retry mechanism and exponential backoff."""
    prompt = f"""
You are an expert digital marketing strategist and copywriter in Pakistan.
Generate a JSON array of exactly {batch_info['count']} realistic, high-converting digital ad records for the Pakistani market.

Niche Category: {batch_info['category']}
Default Industry: {batch_info['industry']}
Specific Context: {batch_info['instructions']}

CRITICAL REQUIREMENTS:
1. Language Diversity:
   - Aggressively mix Pure English, Urdu (Arabic/Nastaliq script like "ابھی آرڈر کریں"), Roman-Urdu ("Fauri rabta karein, bachat ka faida uthayein"), and Mixed language copies.
2. Pakistani Commercial Triggers:
   - Include realistic hooks using local terms: 'fauri', 'bachat', 'dastiyab', 'asli maal', 'chhoot', 'rabta', 'limited stock', 'jaldi karein'.
   - Include realistic pricing (e.g., 'Rs. 1499', 'Rs. 2999', 'PKR 4500', 'Rs. 999'), discount percentages (e.g., '30% off', 'Flat 50% discount'), and delivery terms ('Cash on Delivery', 'Free shipping across Pakistan', 'Muft delivery').
3. CTA Diversity:
   - Use raw CTA strings from: 'SHOP_NOW', 'LEARN_MORE', 'SEND_MESSAGE', 'WHATSAPP_MESSAGE', 'ORDER_NOW', 'CALL_NOW'.
4. Media Types:
   - Mix 'image', 'video', 'carousel'.
5. Days Active:
   - Realistic integers between 2 and 45.

Return STRICTLY a JSON array of objects matching this exact schema:
[
  {{
    "ad_id": "unique_string_id",
    "page_name": "Authentic Pakistani Brand or Agency Name",
    "ad_copy": "Full ad copy text with hooks, body, offer, and CTA trigger",
    "media_type": "image" | "video" | "carousel",
    "cta_raw": "SHOP_NOW" | "LEARN_MORE" | "SEND_MESSAGE" | "WHATSAPP_MESSAGE" | "ORDER_NOW" | "CALL_NOW",
    "days_active": 14,
    "industry": "{batch_info['industry']}",
    "source_type": "curated_seed"
  }}
]
"""
    print(f"\n[+] Generating Batch {batch_index}/{len(BATCHES)}: {batch_info['category']} ({batch_info['count']} ads)...")

    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            raw_text = clean_json_response(response.text)
            data = json.loads(raw_text)

            if not isinstance(data, list):
                raise ValueError(f"Expected a JSON list from Gemini, received {type(data)}")

            validated_records = []
            for item in data:
                try:
                    if not item.get("ad_id") or not isinstance(item["ad_id"], str):
                        item["ad_id"] = f"gen_{uuid.uuid4().hex[:8]}"
                    if not item.get("source_type"):
                        item["source_type"] = "curated_seed"
                    if not item.get("industry"):
                        item["industry"] = batch_info["industry"]

                    record = RawAdRecord(**item)
                    validated_records.append(record)
                except ValidationError as e:
                    print(f"  [!] Skipping invalid record ({item.get('page_name', 'Unknown')}): {e}")

            if not validated_records:
                raise ValueError("No records could be validated from model output.")

            print(f"  [OK] Validated {len(validated_records)}/{len(data)} records for Batch {batch_index}.")
            return validated_records

        except (json.JSONDecodeError, ValueError) as json_err:
            print(f"  [Parse Error] Attempt {attempt}/{max_retries} encountered JSON parsing error: {json_err}")
            if attempt == max_retries:
                raise
            time.sleep(delay)

        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "quota" in exc_str or "resource_exhausted" in exc_str:
                print(f"  [Rate Limit] Attempt {attempt}/{max_retries} hit quota limit: {exc}")
                if attempt == max_retries:
                    raise
                backoff = delay * (2 ** (attempt - 1))
                print(f"  [Backoff] Sleeping {backoff:.1f}s before retrying...")
                time.sleep(backoff)
            else:
                print(f"  [Transient Error] Attempt {attempt}/{max_retries} encountered error: {exc}")
                if attempt == max_retries:
                    raise
                backoff = delay * (2 ** (attempt - 1))
                time.sleep(backoff)

    return []


def generate_curated_fallback_batch(batch_info: dict, batch_index: int) -> List[RawAdRecord]:
    """Synthesizes high-fidelity Pakistani ad records without external API requirement."""
    print(f"\n[+] Synthesizing Batch {batch_index}/{len(BATCHES)}: {batch_info['category']} ({batch_info['count']} ads)...")
    industry = batch_info["industry"]
    templates = CURATED_OFFLINE_TEMPLATES.get(industry, [])
    
    validated_records = []
    for idx, (page, copy, media, cta, days) in enumerate(templates[:batch_info["count"]], start=1):
        rec = RawAdRecord(
            ad_id=f"pk_{industry.lower()}_{idx:03d}",
            page_name=page,
            ad_copy=copy,
            media_type=media,
            cta_raw=cta,
            days_active=days,
            industry=industry,
            source_type="curated_seed",
        )
        validated_records.append(rec)
        
    print(f"  [OK] Successfully synthesized {len(validated_records)} records for Batch {batch_index}.")
    return validated_records


def main():
    print("=" * 60)
    print("  AdLens PK - Synthetic Demo Dataset Generator")
    print("=" * 60)

    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    model = None
    use_gemini = False

    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            use_gemini = True
            print("[+] Gemini API Key detected. Using live LLM generation.")
        except Exception as e:
            print(f"[!] Warning: Could not initialize Gemini client ({e}). Using offline synthesizer.")
    else:
        print("[i] GEMINI_API_KEY not configured. Running high-fidelity Pakistani dataset synthesizer.")

    all_new_records: List[RawAdRecord] = []
    for idx, batch in enumerate(BATCHES, start=1):
        if use_gemini and model:
            try:
                records = generate_batch_with_retry(batch, idx, model)
                all_new_records.extend(records)
                if idx < len(BATCHES):
                    time.sleep(2)
            except Exception as exc:
                print(f"  [!] Gemini generation failed for Batch {idx} ({exc}). Falling back to curated synthesizer.")
                records = generate_curated_fallback_batch(batch, idx)
                all_new_records.extend(records)
        else:
            records = generate_curated_fallback_batch(batch, idx)
            all_new_records.extend(records)

    if not all_new_records:
        print("\n[!] No records were generated.")
        sys.exit(1)

    # Load existing mock ads
    existing_records = []
    existing_ids = set()
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                raw_existing = json.load(f)
                for item in raw_existing:
                    rec = RawAdRecord(**item)
                    existing_records.append(rec)
                    existing_ids.add(rec.ad_id)
            print(f"\n[+] Loaded {len(existing_records)} existing records from {os.path.basename(DATA_FILE_PATH)}")
        except Exception as e:
            print(f"[!] Warning reading existing {DATA_FILE_PATH}: {e}")

    # Deduplicate IDs for new records
    added_records = []
    for rec in all_new_records:
        unique_id = rec.ad_id
        counter = 1
        while unique_id in existing_ids:
            unique_id = f"{rec.ad_id}_{counter}"
            counter += 1
        rec.ad_id = unique_id
        existing_ids.add(unique_id)
        added_records.append(rec)

    combined_records = existing_records + added_records
    serialized_data = [r.model_dump() for r in combined_records]

    # Save to mock_ads.json
    os.makedirs(os.path.dirname(DATA_FILE_PATH), exist_ok=True)
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(serialized_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"  SUCCESS: Added {len(added_records)} new ads to mock dataset.")
    print(f"  Total records in {os.path.basename(DATA_FILE_PATH)}: {len(combined_records)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
