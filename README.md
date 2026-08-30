# AdLens PK

> Pakistan's First Longitudinal Digital Ad Intelligence and Creative Strategy Engine

AdLens PK is a specialized ad intelligence, competitor tracking, and creative strategy platform engineered for the Pakistani digital commerce and direct-to-consumer (D2C) advertising ecosystem. It bridges the gap left by international ad intelligence tools by incorporating native Roman-Urdu NLP models, deterministic commercial mechanic extraction (Cash on Delivery, WhatsApp funnels, PKR pricing thresholds), and macroeconomic consumer transaction data.

---

## Features

- **6-Tab PyQt6 Desktop Application**: Fully native, dark-themed desktop interface built with PyQt6 and PyQtGraph, providing interactive analytical views: Market Overview, Offer Matrix, Hook Psychology, Strategy Playbook, Trend Tracker, and Competitor Watchlist.
- **Playwright Web Scraper with Bot Detection Hardening**: Automated extraction engine using Chromium with anti-fingerprint hardening, random mouse movements, variable scroll cadence, and persistent browser storage states to safely collect active ads from the public Facebook Ad Library for Pakistan.
- **APScheduler Automated 6-Hour Ingestion**: Background scheduling engine running recurring 6-hour ingestion cycles across all major commercial industries (Fashion, Electronics, Food & Grocery, Health & Beauty, Real Estate, Education, and General Retail).
- **SQLite Local Database with Longitudinal Storage**: Relational persistence layer managed via SQLAlchemy, storing full ad copy, advertiser identities, historical timestamps, pricing models, CTA configurations, and hook types for long-term trend analysis.
- **Ad Longevity Intelligence**: Evaluates active campaign lifespans (days active) as an objective proxy for ad profitability and scaling success in the Pakistani media buying landscape.
- **Competitor Watchlist with Auto-Detection**: Dedicated monitoring view that enables users to track target competitor brand pages, automatically detecting and updating ad counts and activity timestamps whenever new ad records are ingested.
- **One-Click PDF Report Export**: Generates professional, multi-page tactical strategy summaries and executive intelligence briefs ready for client presentations and agency workflows.
- **Kaggle Demand Context (521k Real Transactions)**: Integrates Pakistan's Largest Ecommerce Dataset by zusmani to benchmark creative ad frequency against half a million verified consumer transactions across top product categories.
- **AI-Powered Strategy Brief via Gemini**: Context-aware LLM synthesis synthesizing market whitespaces, recommended psychological angles, offer structures, and high-converting Roman-Urdu copy hooks tailored to the selected niche.
- **System Tray Background Operation**: Runs persistently in the background with status bar diagnostics, database counter metrics, and scheduled execution indicators without interrupting desktop workflows.
- **Docker Compose Deployment**: Full containerization configuration supporting reproducible multi-service deployment with PostgreSQL and backend workers.

---

## Technical Architecture

```
                                    +-----------------------------------------+
                                    |         Data Ingestion Layer            |
                                    |  - Playwright Scraper (Stealth Browser) |
                                    |  - Meta Ad Library Graph API            |
                                    |  - APScheduler (6-Hour Ingestion Loop)  |
                                    +--------------------+--------------------+
                                                         |
                                                         v
                                    +--------------------+--------------------+
                                    |       Core Intelligence Pipeline        |
                                    |  - Vernacular Roman-Urdu Classifier     |
                                    |  - Deterministic Commercial Extractor   |
                                    |  - Kaggle E-Commerce Demand Enricher    |
                                    |  - Google Gemini Strategy Engine        |
                                    +--------------------+--------------------+
                                                         |
                                                         v
                                    +--------------------+--------------------+
                                    |     Database & Persistence Layer        |
                                    |  - SQLAlchemy ORM                       |
                                    |  - SQLite (Local) / PostgreSQL (Prod)   |
                                    |  - Watchlist & Longitudinal Tracking    |
                                    +--------------------+--------------------+
                                                         |
                                                         v
                                    +--------------------+--------------------+
                                    |         PyQt6 Desktop Client            |
                                    |  - Market Overview & Longevity Stats    |
                                    |  - Offer Matrix & CTA Analysis          |
                                    |  - Hook Psychology & Language Breakdown |
                                    |  - Strategy Playbook & PDF Exporter     |
                                    |  - Trend Tracker & Competitor Watchlist |
                                    +-----------------------------------------+
```

---

## Tech Stack

| Layer | Component | Specification / Purpose |
| --- | --- | --- |
| **Runtime** | Python 3.12 | Core backend language and pipeline runtime |
| **Desktop UI** | PyQt6 & PyQtGraph | Hardware-accelerated desktop UI and real-time visualization |
| **Scraper** | Playwright (Async Python) | Headless Chromium automation with anti-bot bypass |
| **Task Scheduler** | APScheduler | Interval-based background job orchestration |
| **Database** | SQLite / PostgreSQL | Relational storage for ad copies, classifications, and watchlist entries |
| **ORM Layer** | SQLAlchemy 2.0 | Declarative data modeling, migrations, and transactional queries |
| **AI Synthesis** | Google Gemini API | Structured creative brief generation and whitespace reasoning |
| **Market Data** | Pandas | High-speed processing of 521k+ transactions from Kaggle |
| **Testing** | Pytest | Comprehensive unit and integration test suite |
| **Containerization** | Docker & Docker Compose | Multi-container reproducible runtime configuration |

---

## Project Structure

```
adlens-pk/
|-- src/
|   |-- config/
|   |   +-- settings.py            # Environment configuration and API keys
|   |-- core/
|   |   |-- ai_engine.py           # Gemini-powered creative brief synthesis
|   |   |-- classifier.py          # Language detection and hook classification
|   |   |-- extractor.py           # Regex-based commercial and CTA extraction
|   |   |-- fetcher.py             # Live Meta API and local demo dataset fetcher
|   |   |-- kaggle_enricher.py     # Kaggle 521k order dataset demand benchmark
|   |   |-- scheduler.py           # APScheduler 6-hour background ingestion loop
|   |   |-- schemas.py             # Pydantic data contracts and models
|   |   +-- scraper.py             # Playwright Facebook Ad Library stealth scraper
|   |-- db/
|   |   |-- models.py              # SQLAlchemy AdRecord schema
|   |   |-- repository.py          # Database operations and trend aggregations
|   |   +-- watchlist.py           # Competitor Watchlist ORM model and CRUD
|   |-- desktop/
|   |   +-- main_window.py         # 6-tab PyQt6 desktop application
|   +-- data/
|       |-- mock_ads.json          # Curated seed ad intelligence dataset
|       +-- kaggle/                # Kaggle e-commerce transaction CSV directory
|-- tests/
|   +-- test_pipeline.py           # Unit and integration test suite (35 tests)
|-- scripts/
|   |-- test_kaggle_real.py        # Kaggle dataset verification script
|   |-- test_scraper.py            # Playwright scraper smoke test
|   +-- test_db.py                 # SQLite database query verification
|-- docker-compose.yml             # Multi-service container definitions
|-- Dockerfile                     # Application container build instructions
|-- requirements.txt               # Python package dependencies
+-- README.md                      # Project documentation
```

---

## Installation & Setup

### Prerequisites

- Python 3.12 or higher
- Git
- Google Gemini API Key (optional for offline demo mode)
- Kaggle Account & API Token (optional for demand benchmarking)

### 1. Clone the Repository

```bash
git clone https://github.com/Muhammad-Kamal-Asif/adlens-pk.git
cd adlens-pk
```

### 2. Create Virtual Environment and Install Dependencies

```bash
python -m venv .venv

# On Windows
.\.venv\Scripts\activate

# On Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```ini
GEMINI_API_KEY=your_gemini_api_key_here
META_API_TOKEN=your_meta_graph_api_token_here
DATABASE_URL=sqlite:///./adlens_local.db
USE_MOCK_DATA=True
```

### 4. Optional: Download Kaggle Dataset

To enable real-world transaction demand benchmarking, download the dataset into `src/data/kaggle/`:

```bash
kaggle datasets download -d zusmani/pakistans-largest-ecommerce-dataset -p src/data/kaggle --unzip
```

---

## Running the Application

### Launch PyQt6 Desktop Client

```bash
python src/desktop/main_window.py
```

### Run via Docker Compose

```bash
docker-compose up --build
```

---

## Running the Test Suite

The test suite validates data schemas, deterministic extractors, language classifiers, Kaggle dataset loading, scheduler workflows, database models, and PyQt6 desktop UI events:

```bash
pytest -v
```

---

## Author

Developed by **Muhammad Kamal**
