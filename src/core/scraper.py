import asyncio
import logging
import re
import random
from pathlib import Path
from typing import List

from src.core.schemas import RawAdRecord
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_BROWSER_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "browser_state.json"

_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--window-size=1366,768",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# FIX 1 — JS filter: exclude country-selector dropdown and noise-heavy divs.
_EXTRACT_JS = """() => {
    const ads = [];
    const allDivs = document.querySelectorAll('div');

    for (const div of allDivs) {
        const text = div.innerText || "";

        // FIX 1: skip country-selector dropdown and divs with excessive newlines
        if (text.includes("Afghanistan") || (text.split("\\n").length > 50)) {
            continue;
        }

        if (
            text.length > 150 && text.length < 3000 &&
            !text.includes("Log in") && !text.includes("Create account")
        ) {
            let hasMatchingChild = false;
            for (const child of div.children) {
                if (child.tagName === "DIV") {
                    const childText = child.innerText || "";
                    if (
                        childText.length > 150 && childText.length < 3000 &&
                        !childText.includes("Log in") && !childText.includes("Create account") &&
                        !childText.includes("Afghanistan") &&
                        childText.split("\\n").length <= 50
                    ) {
                        hasMatchingChild = true;
                        break;
                    }
                }
            }

            if (!hasMatchingChild) {
                const lines = text.split("\\n").map(l => l.trim()).filter(l => l.length > 0);
                if (lines.length > 0) {
                    const advertiser = lines[0];
                    const daysRunningText = lines.find(
                        l => l.toLowerCase().includes("started running on") ||
                             l.toLowerCase().includes("running")
                    ) || null;
                    const adBody = lines.filter(l => l !== advertiser).join(" ");
                    ads.push({
                        advertiser_name: advertiser,
                        ad_body: adBody,
                        days_running: daysRunningText
                    });
                }
            }
        }
    }
    return ads;
}"""


async def _random_mouse_moves(page, count: int = 3) -> None:
    """FIX 4: Simulate human-like random mouse movements."""
    for _ in range(count):
        x = random.randint(100, 1266)
        y = random.randint(100, 668)
        await page.mouse.move(x, y)
        await page.wait_for_timeout(random.randint(80, 200))


async def scrape_facebook_ads(industry: str, max_ads: int = 100) -> List[RawAdRecord]:
    """Scrapes the public Facebook Ad Library for a given industry."""
    results: List[RawAdRecord] = []

    try:
        async with async_playwright() as p:
            # FIX 5: harden launch args
            browser = await p.chromium.launch(
                headless=True,
                args=_LAUNCH_ARGS,
            )

            # FIX 8: load saved session state if available
            context_kwargs = dict(
                locale="en-PK",
                timezone_id="Asia/Karachi",
                viewport={"width": 1366, "height": 768},
                user_agent=_USER_AGENT,
            )
            if _BROWSER_STATE_PATH.exists():
                logger.info("Loading saved browser state.")
                context_kwargs["storage_state"] = str(_BROWSER_STATE_PATH)

            # FIX 3: realistic browser profile
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            # FIX 6: strip webdriver fingerprint before any navigation
            await page.add_init_script(
                "delete Object.getPrototypeOf(navigator).webdriver"
            )

            # Navigate to the Ad Library directly
            url = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=PK&q={industry}"
            logger.info(f"Navigating to {url}")
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # Wait for results to begin loading
            await page.wait_for_timeout(5000)

            try:
                await page.wait_for_selector("div", timeout=5000)
            except Exception as e:
                logger.debug(f"Timeout waiting for div selector: {e}")

            # FIX 4: scroll with random delays and mouse movements between each scroll
            for _ in range(5):
                await _random_mouse_moves(page, count=2)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                # FIX 4: random delay 1500–4000 ms between scrolls
                await page.wait_for_timeout(random.randint(1500, 4000))

            # FIX 1: extract with country-selector and newline-count filters
            extracted_data = await page.evaluate(_EXTRACT_JS)

            # FIX 8: persist storage state after a successful scrape
            if extracted_data:
                try:
                    _BROWSER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(_BROWSER_STATE_PATH))
                    logger.info(f"Browser state saved to {_BROWSER_STATE_PATH}.")
                except Exception as e:
                    logger.warning(f"Could not save browser state: {e}")

            await browser.close()

            for data in extracted_data:
                if len(results) >= max_ads:
                    break

                days_active = 1
                days_running_text = data.get("days_running")
                if days_running_text:
                    match = re.search(r"\d+", days_running_text)
                    if match:
                        days_active = int(match.group())

                results.append(
                    RawAdRecord(
                        source_type="playwright_scrape",
                        page_name=data.get("advertiser_name"),
                        ad_copy=data.get("ad_body"),
                        industry=industry,
                        days_active=days_active,
                    )
                )

    except Exception as e:
        logger.error(f"Error scraping Facebook ads: {e}")
        return []

    if results:
        from src.db.watchlist import check_and_update_watchlist
        check_and_update_watchlist(results)

    return results


def scrape_ads_sync(industry: str, max_ads: int = 100) -> List[RawAdRecord]:
    """Synchronous wrapper that runs the async scraper via asyncio.run()."""
    return asyncio.run(scrape_facebook_ads(industry, max_ads))
