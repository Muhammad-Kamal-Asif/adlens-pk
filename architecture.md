# AdLens PK — Comprehensive Technical Architecture & Execution Blueprint

> **Project:** AdLens PK — AI-Powered Pakistani Digital Ad Intelligence Engine  
> **Status:** Specification & Contract Definition  
> **Maintainer:** Muhammad Kamal  
> **License:** MIT  

---

## 1. Executive Summary & Problem Space

### 1.1 The Core Problem
Pakistani digital marketing agencies, D2C brands, and local SMEs waste significant ad spend due to a critical lack of localized competitive intelligence. Global competitive intelligence platforms (e.g., AdSpy, Foreplay) present three major barriers:
1. **Cost Inaccessibility:** Pricing tiers ($100–$300/mo) are prohibitive for local agencies and SMBs.
2. **Vernacular Blindspots:** Global tools lack tokenization and NLP support for Roman-Urdu, Urdu script, and local colloquial buying triggers (*"fauri rabta"*, *"bachat"*, *"asli maal"*).
3. **Ignored Local Commercial Dynamics:** Global tools fail to extract Pakistan-specific commercial realities, specifically Cash-on-Delivery (COD) friction, WhatsApp-first checkout funnels, and localized delivery thresholds.

### 1.2 The Solution
**AdLens PK** is a specialized ad intelligence and creative strategy pipeline that ingests Pakistani digital ad records, extracts commercial terms deterministically, classifies psychological hooks across English and Roman-Urdu using AI, and outputs automated creative campaign playbooks.

---

## 2. Decoupled 4-Tier System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          1. INGESTION LAYER                            │
│  src/core/fetcher.py                                                   │
│  - Dual-Engine Strategy: Live API Wrapper + Seed Dataset Fallback      │
│  - Standardizes payload into RawAdRecord schema                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Strict Schema: RawAdRecord)
┌───────────────────────────────────▼────────────────────────────────────┐
│                    2. DETERMINISTIC EXTRACTION LAYER                   │
│  src/core/extractor.py                                                 │
│  - Regex & Rule-Based Parser (Price, COD, Delivery, CTA)               │
│  - Roman-Urdu Intent Keyword Matching                                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Strict Schema: AdOfferDetails / OfferMatrix)
┌───────────────────────────────────▼────────────────────────────────────┐
│                   3. AI CLASSIFICATION & REASONING                     │
│  src/core/classifier.py & src/core/ai_engine.py                        │
│  - Opening Hook Isolator (First 1-2 sentences)                         │
│  - Language Detector (English / Urdu / Roman-Urdu / Mixed)             │
│  - Psychological Hook Classifier (Problem-Agitation, Social Proof, etc)│
│  - Strategy Brief Synthesizer (Creative Whitespace Analysis)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Strict Schema: HookAnalysisReport & TacticalCreativeBrief)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        4. PRESENTATION LAYER                           │
│  src/ui/app.py                                                         │
│  - Streamlit Modular Dashboard (Overview, Offer Matrix, Hook Studio)   │
│  - Strategy Brief Generator & Markdown Export                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Layout & Module Responsibilities

```
adlens-pk/
├── .env.example                # Environment variable templates
├── .gitignore                  # Standard Python ignore rules
├── LICENSE                     # MIT License
├── requirements.txt            # Project dependencies
├── architecture.md             # This comprehensive architecture document
│
└── src/
    ├── config/
    │   ├── __init__.py
    │   └── settings.py         # Pydantic BaseSettings management
    │
    ├── core/
    │   ├── __init__.py
    │   ├── schemas.py          # Strict Pydantic contracts across all boundaries
    │   ├── fetcher.py          # Ingestion engine (API wrapper + Mock JSON loader)
    │   ├── extractor.py        # Deterministic regex & commercial term extractor
    │   ├── classifier.py       # Hook & Language classification engine
    │   └── ai_engine.py        # LLM integration (Gemini / Qwen API orchestration)
    │
    ├── ui/
    │   ├── __init__.py
    │   └── app.py              # Streamlit multi-tab analytical interface
    │
    └── data/
        └── mock_ads.json       # Seeded database of 200+ curated Pakistani ads
```

---

## 4. Strict Schema Contracts (`src/core/schemas.py`)

All communication between modules is governed by immutable Pydantic models:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# --- Layer 1: Ingestion Contract ---
class RawAdRecord(BaseModel):
    ad_id: str
    page_name: str
    ad_copy: str
    media_type: Literal["image", "video", "carousel", "unknown"] = "image"
    cta_raw: Optional[str] = "LEARN_MORE"
    days_active: int = 1
    industry: str
    source_type: Literal["curated_seed", "live_api"] = "curated_seed"

# --- Layer 2: Deterministic Extraction Contracts ---
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

# --- Layer 3: AI Hook Classification & Brief Contracts ---
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
```

---

## 5. Technical Implementation Mechanics

### 5.1 Ingestion Layer (`src/core/fetcher.py`)

* Implements `fetch_ads(industry: str, use_mock: bool = True) -> List[RawAdRecord]`.
* If `use_mock=True` or if the live API fails/times out, reads directly from `src/data/mock_ads.json`.
* Guarantees zero unhandled exceptions to the upstream layers.

### 5.2 Deterministic Extraction Layer (`src/core/extractor.py`)

* Evaluates `ad_copy` without relying on non-deterministic LLM calls for structured fields.
* **Regex Patterns:** Extracts PKR pricing (`Rs.?\s?\d+[\d,]*`, `PKR\s?\d+`), discount percentages (`\d+%\s?off`), and delivery terms (`free delivery`, `muft delivery`).
* **Urdu/Roman-Urdu Triggers:** Identifies keywords like `COD`, `cash on delivery`, `fauri`, `bachat`, `rabta`.
* Maps raw CTA metadata into standardized categories.

### 5.3 AI Classification & Reasoning (`src/core/classifier.py` & `src/core/ai_engine.py`)

* **Hook Extraction:** Isolates the first 1–2 sentences of the ad body.
* **Language Detection:** Identifies script/lexical patterns (English vs. Nastaliq script vs. Romanized Urdu transliteration).
* **LLM Reasoning (Gemini / Qwen API):** Prompts the model with strict JSON schema constraints to classify psychological angles and generate the `TacticalCreativeBrief`.

### 5.4 Presentation Layer (`src/ui/app.py`)

* Tab 1: **Market Overview & Metrics** (Active ads, average duration, language split).
* Tab 2: **Pakistan Offer Matrix** (COD adoption, free delivery prevalence, CTA distribution).
* Tab 3: **Hook Psychology Studio** (Interactive hook explorer filtered by type and language).
* Tab 4: **AI Strategy Generator** (One-click tactical brief creation and Markdown download).

---

## 6. Build Order & Phase Roadmap

| Phase | Module | Output Deliverable |
| --- | --- | --- |
| **Phase 1** | `src/core/schemas.py` & `src/data/mock_ads.json` | Complete data contracts + seeded 200+ Pakistani ad dataset |
| **Phase 2** | `src/core/fetcher.py` & `src/core/extractor.py` | Data loading and deterministic regex extraction validated |
| **Phase 3** | `src/core/classifier.py` & `src/core/ai_engine.py` | AI hook classification and creative brief generation tested |
| **Phase 4** | `src/ui/app.py` | Streamlit user interface fully wired to backend contracts |
| **Phase 5** | Containerization & Deployment | Dockerfile verified and deployed to Alibaba Cloud ECS |
