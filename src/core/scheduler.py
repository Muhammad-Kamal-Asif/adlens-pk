import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.core.fetcher import fetch_ads, INDUSTRY_SEARCH_TERMS
from src.core.scraper import scrape_ads_sync
from src.db.repository import save_ads

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _ingest_all_industries() -> None:
    """Scrapes ads for every configured industry and persists them, falling back to mock data if empty."""
    logger.info("Starting scheduled ad ingestion for all industries.")

    for industry in INDUSTRY_SEARCH_TERMS.keys():
        try:
            ads = scrape_ads_sync(industry=industry, max_ads=50)
            if not ads:
                logger.warning(
                    f"Scraper returned no ads for industry '{industry}'. Falling back to local dataset."
                )
                ads = fetch_ads(industry=industry, use_mock=True)

            if ads:
                saved_count = save_ads(ads)
                logger.info(f"Ingested {saved_count} new ads for industry '{industry}'.")
            else:
                logger.warning(f"No ads returned for industry '{industry}'.")
        except Exception as e:
            logger.error(f"Scheduled ingestion failed for industry '{industry}': {e}")
            try:
                fallback_ads = fetch_ads(industry=industry, use_mock=True)
                if fallback_ads:
                    saved_count = save_ads(fallback_ads)
                    logger.info(f"Ingested {saved_count} fallback mock ads for industry '{industry}'.")
            except Exception as fallback_err:
                logger.error(f"Fallback ingestion failed for industry '{industry}': {fallback_err}")

    logger.info("Scheduled ad ingestion complete.")


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler that ingests live ads every 6 hours."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler is already running.")
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _ingest_all_industries,
        trigger=IntervalTrigger(hours=6),
        id="adlens_ingest_all_industries",
        name="AdLens PK - Ingest live ads for all industries",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("AdLens PK scheduler started with 6-hour interval.")

    return _scheduler


def stop_scheduler() -> None:
    """Stop the background scheduler gracefully."""
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        logger.warning("Scheduler is not running.")
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("AdLens PK scheduler stopped.")
