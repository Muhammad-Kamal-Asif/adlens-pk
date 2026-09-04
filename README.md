# AdLens PK — Pakistani Ad Intelligence Engine

Pakistan's first longitudinal ad intelligence engine. Scrapes real Pakistani Facebook ads, stores them historically, and surfaces competitive intelligence for local marketers and SMEs.

## The Problem

Pakistani brand owners spend Rs. 50,000+ per month on Facebook ads with zero visibility into what competitors are doing. Global tools like BigSpy and AdSpy cost $150-300/month and have no understanding of Pakistani commercial mechanics — Cash on Delivery, PKR pricing, WhatsApp CTAs, or Roman-Urdu copy.

## What AdLens PK Does

- Scrapes Facebook Ad Library in real-time with card-by-card visual extraction
- Stores Pakistani ad data historically — the database compounds over time
- Extracts Pakistan-specific signals: COD prevalence, PKR price bands, WhatsApp CTA rates
- Surfaces competitive intelligence: which hook types win, which brands are most active, what ad patterns survive longest
- Runs on a 6-hour automated schedule — data grows without manual intervention

## Current Database

- 3,073+ real Pakistani ads tracked
- 14 industries covered: Fashion, Electronics, Real Estate, Food, Health, Education, Home, General and more
- Top advertiser: PhoneCase Pakistan
- Most active industry: Fashion (848 ads)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop UI | PyQt6 |
| Web Scraping | Playwright (card-by-card visual extraction) |
| Database | SQLite with SQLAlchemy ORM |
| ML Pipeline | scikit-learn (GradientBoosting + TF-IDF) |
| AI Briefs | Google Gemini |
| Scheduling | APScheduler (6-hour automated pulls) |
| Market Data | Kaggle Pakistan Ecommerce Dataset (521k transactions) |
| CLI | Python argparse with colorama |

## How to Run

```bash
git clone https://github.com/Muhammad-Kamal-Asif/adlens-pk.git
cd adlens-pk
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Add your GEMINI_API_KEY to .env
python main.py
```

The app opens as a desktop window with 3,073 pre-collected Pakistani ads ready to explore.

## Key Features

**Home Dashboard** — Live market view with 3,073 ads, industry distribution charts, COD adoption rates, top performing brands

**Live Collection** — Watch the scraper run in real-time. Each Facebook ad card glows green as it is extracted. Supports parallel collection across 4 industries simultaneously.

**Winning Formula** — Per-industry analysis of what makes ads run longer: hook types, CTA patterns, COD usage, price ranges

**Price Intelligence** — PKR price band analysis across industries with your price positioning checker

**WhatsApp Intel** — Tracks WhatsApp CTA adoption by industry — critical for Pakistani D2C brands

**Ad Copy Grader** — Score your own ad copy against market patterns

**Competitor Watchlist** — Track specific brands and get alerted when they launch new ads

**ML Training Center** — Local model trains on your data and improves as the database grows

**CLI Mode** — Full command-line interface: fetch, analyze, grade, train, status commands

## Intelligence Pages

1. Home — Live market dashboard
2. Live Collection — Real-time scraper with visual card glow
3. Winning Formula — What makes ads survive
4. Market Overview — Campaign metrics after generating a report
5. Offer Matrix — COD, pricing, CTA analysis
6. Hook Psychology — Psychological angle breakdown
7. Strategy Playbook — AI-generated creative brief
8. Price Intelligence — PKR price band analysis
9. WhatsApp Intel — WhatsApp CTA adoption
10. Trend Tracker — Longitudinal trend analysis
11. Trend Velocity — Market momentum indicators
12. Ad Grader — Score your own copy
13. Brand Profile — Deep dive into any brand
14. ML Training — Local model management
15. Watchlist — Competitor monitoring
16. Report History — Browse past reports

## Built by

Muhammad Kamal — BBA Student, University of Sargodha
