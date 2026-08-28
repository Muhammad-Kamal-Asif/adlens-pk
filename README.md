# AdLens PK — Pakistani Digital Ad Intelligence & Creative Playbook Engine

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![Validation](https://img.shields.io/badge/Schema-Pydantic%20V2-red.svg)](https://docs.pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Hackathon](https://img.shields.io/badge/Bano%20Qabil%20x%20Alibaba%20Cloud-AI%20Hackathon-orange.svg)](https://banoqabil.pk)

**AdLens PK** is a localized competitive ad intelligence and AI creative playbook engine specifically tailored for the Pakistani digital advertising and e-commerce ecosystem. It bridges the critical gap left by global competitive intelligence tools by understanding Roman-Urdu nuances, Cash-on-Delivery (COD) dynamics, and local consumer psychology.

---

## 🚀 Quick Start

Get AdLens PK up and running locally in under 2 minutes:

### 1. Clone & Set Up Environment
```bash
# Clone the repository
git clone https://github.com/Muhammad-Kamal-Asif/adlens-pk.git
cd adlens-pk

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (CMD):
.\.venv\Scripts\activate.bat
# Linux / macOS / Git Bash:
source .venv/bin/activate
```

### 2. Install Requirements
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
streamlit run src/ui/app.py
```
*The interactive dashboard will automatically open in your default browser at `http://localhost:8501`.*

> [!NOTE]
> **Demo Data Note:** AdLens PK comes pre-loaded with **50 curated, realistic Pakistani ad campaigns** across E-Commerce, EdTech, and Digital Marketing agencies. You can immediately explore market metrics, the Pakistan Offer Matrix, Hook Psychology, and AI playbooks with **zero API configuration required**.

---

## 📌 Problem Space & Market Need

Pakistani D2C e-commerce brands, digital agencies, and SMEs waste substantial ad spend due to a severe lack of actionable, localized market intelligence:

1. **Prohibitive Global Tool Pricing:** Platforms like AdSpy and Foreplay cost $100–$300+/month, placing them far out of reach for Pakistani startups, solo media buyers, and local agencies.
2. **Vernacular & Roman-Urdu Blindspots:** Global tools lack tokenization and NLP support for Roman-Urdu, Urdu script, and colloquial commercial triggers (*"fauri rabta"*, *"bachat sale"*, *"asli maal"*, *"dastiyab"*).
3. **Local Commercial Realities Ignored:** Over 80% of Pakistani e-commerce relies on Cash on Delivery (COD) and WhatsApp-first checkout funnels. Standard tools do not extract or quantify COD adoption, delivery thresholds, or local PKR price mechanics (`Rs. 1499`).

### 💡 The AdLens PK Solution
AdLens PK ingests local digital ad records, extracts commercial terms deterministically (price points, discounts, COD, delivery incentives, CTA normalization), classifies psychological hook angles across English and Roman-Urdu, and synthesizes high-converting creative playbooks powered by LLMs (Google Gemini).

---

## 🏆 Alignment with Bano Qabil & Alibaba Cloud AI Hackathon

AdLens PK was engineered for the **Bano Qabil & Alibaba Cloud AI Hackathon** with the following foundational pillars:

- **Grassroots Empowerment:** Democratizing enterprise-grade competitive intelligence for Pakistani youth, freelancers, and small business owners.
- **Vernacular-First AI:** Solving real socio-economic problems in emerging markets through localized Natural Language Processing and commercial heuristic analysis.
- **Cloud-Native & Scalable:** Designed for containerized deployment on **Alibaba Cloud Elastic Compute Service (ECS)** and **Container Service for Kubernetes (ACK)** with cost-effective inference pipelines.

---

## 🏗️ 4-Tier Decoupled Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          1. INGESTION LAYER                            │
│  src/core/fetcher.py                                                   │
│  - Dual-Engine: Live API Wrapper + Curated Seed Dataset Fallback       │
│  - Standardizes raw data into RawAdRecord schema                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (RawAdRecord)
┌───────────────────────────────────▼────────────────────────────────────┐
│                    2. DETERMINISTIC EXTRACTION LAYER                   │
│  src/core/extractor.py                                                 │
│  - Regex & Rule Engine: Price (PKR/Rs.), Discounts, COD & Free Delivery│
│  - Vernacular intent trigger extraction & CTA normalization            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (AdOfferDetails / OfferMatrixSummary)
┌───────────────────────────────────▼────────────────────────────────────┐
│                   3. AI CLASSIFICATION & REASONING                     │
│  src/core/classifier.py & src/core/ai_engine.py                        │
│  - Language Detection (English / Urdu / Roman-Urdu / Mixed)            │
│  - Psychological Hook Classifier (Problem-Agitation, FOMO, etc.)       │
│  - Gemini LLM Tactical Creative Brief Synthesizer (with offline backup)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (HookAnalysisReport & TacticalCreativeBrief)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        4. PRESENTATION LAYER                           │
│  src/ui/app.py                                                         │
│  - Interactive Streamlit Dashboard (Overview, Matrix, Studio, Brief)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

- **📊 Market Overview & Metrics:** High-level campaign aggregation, language breakdown, and active duration tracking.
- **💰 Pakistan Offer Matrix:** Instant quantification of Cash-on-Delivery (COD) adoption rate, free delivery prevalence, and detected PKR price brackets.
- **🧲 Hook Psychology Studio:** Categorizes creative hooks into *Problem-Agitation*, *Direct Offer / Discount*, *Social Proof / Trust*, *Curiosity / Question*, and *Urgency / FOMO*.
- **🚀 AI Creative Playbook Synthesizer:** Identifies market creative whitespaces, recommends psychological angles, and outputs ready-to-test Roman-Urdu/English copy hooks.
- **📥 One-Click Playbook Export:** Download structured creative briefs as `.txt` files directly from the dashboard.
- **🛡️ 100% Offline Demo Resilience:** Pre-loaded with 50 curated ads and a deterministic fallback strategy engine for reliable offline presentations.

---

## ⚙️ Configuration & Environment (`.env`)

For live AI brief synthesis via Google Gemini or live API queries, configure `.env`:

```bash
cp .env.example .env
```

```env
# Meta Ad Library API token (optional — leave blank to use mock data)
META_API_TOKEN=

# Google Gemini API key (optional — needed for live Gemini 1.5 Flash synthesis)
GEMINI_API_KEY=

# Set to True to run in demo mode using the 50 pre-loaded ads
USE_MOCK_DATA=True
```

---

## 📁 Project Structure

```
adlens-pk/
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore rules
├── .streamlit/
│   └── config.toml             # Dark mode UI configuration
├── architecture.md             # Detailed engineering specifications
├── Dockerfile                  # Container deployment configuration
├── README.md                   # Project documentation
├── requirements.txt            # Python dependencies
├── run.sh                      # One-click startup script
├── scripts/
│   └── generate_demo_data.py   # Automated 45-ad synthetic dataset generator
├── src/
    ├── config/
    │   ├── __init__.py
    │   └── settings.py         # Pydantic BaseSettings & .env management
    ├── core/
    │   ├── __init__.py
    │   ├── schemas.py          # Strict Pydantic models for all data layers
    │   ├── fetcher.py          # Dual ingestion engine (Live API + Mock loader)
    │   ├── extractor.py        # Deterministic regex & commercial parser
    │   ├── classifier.py       # Hook & Language classification heuristics
    │   └── ai_engine.py        # Gemini AI reasoning & fallback synthesizer
    ├── data/
    │   └── mock_ads.json       # Pre-loaded database of 50 Pakistani ads
    └── ui/
        ├── __init__.py
        └── app.py              # Streamlit multi-tab analytical interface
```

---

## 🛠️ Tech Stack

- **Core Backend:** Python 3.10+, [Pydantic V2](https://docs.pydantic.dev/), [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Data & Parsing:** Pandas, Regular Expressions (Regex)
- **AI & LLM Reasoning:** [Google Generative AI (Gemini 1.5 Flash)](https://ai.google.dev/)
- **Frontend Dashboard:** [Streamlit](https://streamlit.io/)
- **Target Deployment:** Alibaba Cloud ECS / Container Service for Kubernetes (ACK)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 👥 Contributors & Acknowledgements

- **Maintainer:** Muhammad Kamal
- **Event:** Bano Qabil & Alibaba Cloud AI Hackathon
