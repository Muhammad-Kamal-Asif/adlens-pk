# AdLens PK — Technical Architecture & Build Blueprint

> **Status:** Submission Ready — September 2026  
> **Maintainer:** Muhammad Kamal  
> **Stack:** Python 3.12, PyQt6, SQLite, Playwright, scikit-learn, Docker Compose, Alibaba Cloud

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
| Playwright visual scraper (card-by-card) | src/core/scraper.py | Complete |
| Ad relevance filter (NLP) | src/core/relevance.py | Complete |
| Season tagger | src/core/season_tagger.py | Complete |
| Price intelligence module | src/core/price_intelligence.py | Complete |
| WhatsApp analyzer | src/core/whatsapp_analyzer.py | Complete |
| SQLite persistence layer | src/db/repository.py, models.py | Complete |
| Report history & auto-save | src/db/reports.py | Complete |
| Competitor watchlist | src/db/watchlist.py | Complete |
| Dedup with stable ID regeneration | src/db/repository.py | Complete |
| Home dashboard (auto-loading) | src/desktop/main_window.py | Complete |
| Winning Formula page | src/desktop/pages/formula_page.py | Complete |
| Market Overview page | src/desktop/main_window.py | Complete |
| Offer Matrix page | src/desktop/main_window.py | Complete |
| Hook Psychology page | src/desktop/main_window.py | Complete |
| Strategy Playbook page | src/desktop/main_window.py | Complete |
| Trend Tracker page | src/desktop/main_window.py | Complete |
| Brand Profile page | src/desktop/main_window.py | Complete |
| Price Intel page | src/desktop/pages/price_page.py | Complete |
| WhatsApp Intel page | src/desktop/pages/whatsapp_page.py | Complete |
| Ad Grader page | src/desktop/pages/grader_page.py | Complete |
| Trend Velocity page | src/desktop/pages/velocity_page.py | Complete |
| ML Training page | src/desktop/pages/ml_training_page.py | Complete |
| ML pipeline (feature builder, trainer, predictor) | src/ml/ | Complete |
| ML model scheduler hook | src/ml/scheduler_hook.py | Complete |
| Analytics trend engine | src/analytics/trend_engine.py | Complete |
| CLI interface | src/cli/cli.py | Complete |
| PDF export | src/core/exporter.py | Complete |
| System tray + scheduler | src/desktop/main_window.py | Complete |
| PyQt6 desktop app (16 pages) | src/desktop/main_window.py + pages/ | Complete |
| Green theme throughout | src/desktop/ + src/core/scraper.py | Complete |
| Playwright scraper with visual card glow | src/core/scraper.py | Complete |
| Parallel collection mode | src/desktop/main_window.py, scripts/batch_collect.py | Complete |
| Dynamic search term generation | scripts/batch_collect.py | Complete |
| Custom keyword UI | src/desktop/main_window.py | Complete |
| APScheduler 6-hour automation | src/core/scheduler.py, src/ml/scheduler_hook.py | Complete |
| CLI with 6 commands | src/cli/cli.py | Complete |
| ML pipeline (GradientBoosting + relevance classifier) | src/ml/ | Complete |
| PDF export | src/core/exporter.py | Complete |
| System tray | src/desktop/main_window.py | Complete |
| Brand Profile page | src/desktop/main_window.py | Complete |
| Competitor Watchlist | src/db/watchlist.py | Complete |
| Report History | src/db/reports.py | Complete |
| In-app data collection worker | src/desktop/main_window.py | Complete |
| Batch collection script | scripts/batch_collect.py | Complete |
| Test suite (23/23 pass) | tests/test_pipeline.py | Complete |

---

## 4. Roadmap (Post-Hackathon)

- Authenticated Facebook session for higher ad volume
- PostgreSQL on Alibaba Cloud for shared longitudinal database
- User accounts and subscription model
- Alert notifications when watched brands launch new ads
- ML model accuracy improvement as database grows beyond 10,000 ads

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

1. UI polish pass (2-3 hours)
2. Expand data collection search terms (1-2 hours)
3. Docker Compose final validation (1-2 hours)
4. Hackathon submission video (1-2 hours)
