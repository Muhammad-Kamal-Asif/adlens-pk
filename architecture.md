# AdLens PK — Technical Architecture & Build Blueprint

> **Status:** Phase 1-4 Complete (Local) | Phase 5-7 In Progress  
> **Maintainer:** Muhammad Kamal  
> **Stack:** Python 3.12, Streamlit, PostgreSQL, Docker Compose, Alibaba Cloud

---

## 1. The Unique Angle (Why This Exists)

Global ad spy tools (AdSpy, BigSpy, Foreplay) have three hard blindspots for Pakistan:

1. **No vernacular intelligence** — zero support for Roman-Urdu, Urdu script, or local buying triggers (fauri, bachat, asli maal)
2. **No local commercial logic** — COD friction, WhatsApp checkout funnels, PKR pricing psychology are invisible to global tools
3. **No longitudinal memory** — every tool gives you a snapshot of TODAY. Nobody tracks how Pakistani ad trends evolve over time. Nobody has Ramzan vs Eid vs regular-season performance data for PK.

AdLens PK owns that third point. It is the only system that stores Pakistani ad intelligence over time, building a proprietary dataset that cannot be replicated by any global tool.

---

## 2. System Architecture (5 Layers)

```text
┌─────────────────────────────────────────┐
│  LAYER 1: INGESTION                     │
│  fetcher.py                             │
│  - Meta Ad Library API (LIVE, v19.0)    │
│  - Kaggle PK E-commerce Dataset         │
│  - Mock JSON fallback (50 records)      │
└─────────────────┬───────────────────────┘
                  │ RawAdRecord (Pydantic)
┌─────────────────▼───────────────────────┐
│  LAYER 2: PERSISTENCE                   │
│  db/repository.py                       │
│  - PostgreSQL (Alibaba Cloud RDS)       │
│  - Stores every ad pull with timestamp  │
│  - Enables trend queries over time      │
│  - Seasonality tagging (Ramzan/Eid/     │
│    Independence Day/regular)            │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  LAYER 3: DETERMINISTIC EXTRACTION      │
│  extractor.py                           │
│  - PKR pricing regex                    │
│  - COD / WhatsApp CTA detection         │
│  - Roman-Urdu intent keywords           │
│  - Free delivery threshold extraction   │
└─────────────────┬───────────────────────┘
                  │ AdOfferDetails (Pydantic)
┌─────────────────▼───────────────────────┐
│  LAYER 4: AI CLASSIFICATION             │
│  classifier.py + ai_engine.py           │
│  - Language detection (EN/UR/Roman-UR)  │
│  - Hook psychology classification       │
│  - Gemini tactical brief synthesis      │
│  - Seasonal pattern recognition         │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  LAYER 5: PRESENTATION                  │
│  ui/app.py (Streamlit)                  │
│  - Market Overview dashboard            │
│  - Offer Matrix (COD/PKR/CTA)           │
│  - Hook Psychology Studio               │
│  - Trend Tracker (longitudinal charts)  │
│  - AI Strategy Playbook generator       │
└─────────────────────────────────────────┘
```

---

## 3. What Is Built (Done)

| Module | File | Status |
| --- | --- | --- |
| Pydantic schemas | src/core/schemas.py | Complete |
| Mock dataset (50 records) | src/data/mock_ads.json | Complete |
| Deterministic extractor | src/core/extractor.py | Complete |
| Hook classifier | src/core/classifier.py | Complete |
| AI brief engine (Gemini) | src/core/ai_engine.py | Complete |
| Streamlit dashboard (basic) | src/ui/app.py | Running |
| Docker (single container) | Dockerfile | Complete |
| Meta API token | .env | Live (200 OK) |
| Test suite (23/23 pass) | tests/test_pipeline.py | Complete |

---

## 4. What Gets Built Next (The Upgrade)

### Phase 5 — Live API Wiring

**File:** `src/core/fetcher.py`  
Replace `NotImplementedError` with live Meta Ad Library requests using `ad_creative_bodies` field (v19.0+).  
Industries to cycle: fashion, food, electronics, real_estate, health, education.

### Phase 6 — PostgreSQL Persistence Layer (The Moat)

**New files:** `src/db/models.py`, `src/db/repository.py`  
Every ad pulled gets stored with:
- `pulled_at` timestamp
- `season_tag` (Ramzan / Eid / Independence Day / regular)
- All extracted fields

This creates trend analysis nobody else has for Pakistan.

### Phase 7 — Kaggle Dataset Integration

**Dataset target:** Pakistani e-commerce consumer behavior (search Kaggle: "Pakistan ecommerce" or "Pakistan consumer")  
Used as: demand-side context layer — what consumers search for vs what brands advertise. The gap between these two is the whitespace insight.

### Phase 8 — Trend Tracker Tab (The Differentiator)

New dashboard tab showing:
- How COD adoption % changes over time
- Which hook types dominate by season
- Rising vs dying ad patterns week over week

### Phase 9 — UI Overhaul

Strip default Streamlit styling. Custom CSS injection: metric cards, dark sidebar, professional SaaS feel.

### Phase 10 — Docker Compose + Alibaba Cloud Deploy

`docker-compose.yml` with two services:
- `app` — Streamlit container
- `db` — PostgreSQL container

Deploy to Alibaba Cloud ECS. Database on Alibaba RDS.

---

## 5. Data Sources

| Source | Type | Purpose |
| --- | --- | --- |
| Meta Ad Library API v19.0 | Live API | Primary ad data (PK) |
| src/data/mock_ads.json | Static JSON | Offline demo fallback |
| Kaggle PK E-commerce dataset | CSV via pandas | Demand-side context |
| PostgreSQL (Alibaba RDS) | Database | Longitudinal storage |

---

## 6. Environment Variables

```bash
META_API_TOKEN=     # Meta Graph API user token
GEMINI_API_KEY=     # Google Gemini API key
DATABASE_URL=       # PostgreSQL connection string
USE_MOCK_DATA=      # True (dev) / False (production)
```

---

## 7. Build Order From Here

1. Wire live API into fetcher.py (1-2 hours)
2. Build PostgreSQL models + repository (2-3 hours)
3. Add docker-compose.yml (1 hour)
4. Integrate Kaggle dataset (2 hours)
5. Build Trend Tracker tab (2-3 hours)
6. UI overhaul (3-4 hours)
7. Deploy to Alibaba Cloud (2 hours)
