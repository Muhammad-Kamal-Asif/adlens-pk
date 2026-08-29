# AdLens PK

> **Pakistan's first longitudinal ad intelligence engine — built for local brands, powered by real data**

---

## The Problem

Global competitive ad intelligence platforms (AdSpy, Foreplay, BigSpy) fail Pakistani brands and agencies because:

* **Vernacular & Roman-Urdu Blindspots:** Global tools lack tokenization and NLP models for Roman-Urdu, Urdu script, and colloquial buying triggers (*"fauri rabta"*, *"bachat"*, *"asli maal"*, *"dastiyab"*).
* **Ignored Local Commercial Realities:** Over 80% of Pakistani digital commerce runs on Cash on Delivery (COD) and WhatsApp-first funnels. Global platforms fail to detect or quantify COD adoption, delivery thresholds, and PKR price mechanics (`Rs. 1499`).
* **Prohibitive Pricing & Ephemeral Data:** Expensive subscriptions ($100–$300/mo) are inaccessible to local SMEs and agencies, while offering zero historical trend tracking or benchmark data for the Pakistani market.

---

## The Solution

**AdLens PK** is an ad intelligence and creative strategy engine built ground-up for the Pakistani digital advertising ecosystem:

* **Longitudinal Ad Storage:** Continuously persists and tracks ad campaigns over time using relational storage, enabling long-term historical trend analysis across industries.
* **Vernacular Roman-Urdu NLP:** Classifies psychological hook angles (*Problem-Agitation*, *Social Proof*, *Curiosity*, *Urgency/FOMO*) and detects language patterns across pure English, Nastaliq Urdu, and Roman-Urdu transliterations.
* **Deterministic COD & Commercial Detection:** High-speed regex parsing extracts PKR pricing, discount percentages, WhatsApp CTAs, free delivery thresholds, and Cash-on-Delivery prevalence.
* **Kaggle Demand Context:** Enriches ad intelligence with real-world consumer order volumes from Pakistan's Largest Ecommerce Dataset (500k+ transactions) to benchmark ad activity against actual category demand.

---

## Tech Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| **Runtime & Language** | Python 3.12 | Core backend pipeline & data processing |
| **Frontend Framework** | Streamlit | Analytical dashboard & interactive UI |
| **Database** | PostgreSQL | Longitudinal ad storage & relational data persistence |
| **ORM & Query Layer** | SQLAlchemy | Data modeling, migrations & schema management |
| **Data Ingestion** | Meta Ad Library API | Live ad ingestion across Pakistani advertisers |
| **AI & LLM Reasoning** | Google Gemini | Psychological hook reasoning & tactical creative brief generation |
| **Market Data** | Kaggle | Pakistan's Largest Ecommerce Dataset demand enrichment |
| **Containerization** | Docker | Reproducible containerized execution & deployment |
| **Cloud Infrastructure** | Alibaba Cloud | Elastic Compute Service (ECS) cloud hosting |

---

## How to Run

```bash
docker-compose up --build
```

---

## Screenshots

[Dashboard Screenshot]

[Trend Tracker Screenshot]

---

## Built by

Built by Muhammad Kamal
