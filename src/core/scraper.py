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

def clean_ad_copy(text: str) -> str:
    import re
    # Remove Library ID lines
    text = re.sub(r'Library ID[:\s]+\d+', '', text)
    # Remove date range patterns
    text = re.sub(r'\d{1,2}\s+\w+\s+\d{4}\s*[-–]\s*\d{1,2}\s+\w+\s+\d{4}', '', text)
    text = re.sub(r'\d{1,2}\s+\w+\s+\d{4}', '', text)
    # Remove platform labels
    for noise in ['Inactive', 'Active', 'Platforms', 'Sponsored', 'All EU countries',
                  'See ad details', 'See Summary', 'About this ad', 'Run on']:
        text = text.replace(noise, '')
    # Remove zero-width characters
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    # Remove lines shorter than 15 chars (usually UI labels)
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) >= 15]
    text = '\n'.join(lines)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


async def scrape_facebook_ads(industry: str, max_ads: int = 100) -> List[RawAdRecord]:
    """Scrapes the public Facebook Ad Library for a given industry."""
    import sys
    results: List[RawAdRecord] = []

    try:
        async with async_playwright() as p:
            # FIX 5: harden launch args
            browser = await p.chromium.launch(
                headless=False,
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

            import urllib.parse
            # Navigate to the Ad Library directly
            url = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=PK&q={urllib.parse.quote(industry)}"
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
                # FIX 4: random delay 2000–3000 ms between scrolls
                await page.wait_for_timeout(random.randint(2000, 3000))

            # STEP 1: Count potential ad cards via JS
            card_count = await page.evaluate("""() => {
                const all = Array.from(document.querySelectorAll('div'));
                const cards = [];
                const seen = new Set();
                for (const div of all) {
                    const text = (div.innerText || '').trim();
                    if (text.length < 80 || text.length > 4000) continue;
                    if (text.includes('Log in') || text.includes('Afghanistan')) continue;
                    const children = Array.from(div.children);
                    const hasMatchingChild = children.some(c => {
                        const ct = (c.innerText || '').trim();
                        return ct.length > 80 && ct.length < 4000;
                    });
                    if (hasMatchingChild) continue;
                    const key = text.substring(0, 60);
                    if (seen.has(key)) continue;
                    seen.add(key);
                    cards.push(true);
                }
                return cards.length;
            }""")
            logger.info(f"JS card count: {card_count}")

            # STEP 2: Process each card individually with visual highlighting
            from datetime import datetime

            card_elements = await page.query_selector_all('div')
            processed = 0
            seen_fingerprints = set()
            noise_list = [
                "Ad Library", "System status", "About", "Privacy", 
                "Terms", "Log in", "Create account", "See more in the Ad Library",
                "Afghanistan"
            ]
            skipped_duplicates = 0
            for element in card_elements:
                if processed >= max_ads:
                    break
                try:
                    raw_text = await element.inner_text()
                    raw_text = raw_text.strip()
                    if len(raw_text) < 80 or len(raw_text) > 4000:
                        continue
                    
                    if any(raw_text.startswith(noise) or noise in raw_text for noise in noise_list):
                        continue

                    text = clean_ad_copy(raw_text)

                    fingerprint = text[:120].replace(' ','').replace('\n','').lower()
                    if fingerprint in seen_fingerprints:
                        skipped_duplicates += 1
                        continue

                    await element.scroll_into_view_if_needed()
                    await page.wait_for_timeout(300)

                    # Add fingerprint only AFTER scroll succeeds — so a
                    # container-div failure doesn't poison its children.
                    seen_fingerprints.add(fingerprint)

                    await page.evaluate("""el => {
                        el.style.outline = '2px solid #e63946';
                        el.style.boxShadow = '0 0 16px rgba(230,57,70,0.7)';
                        el.style.borderRadius = '8px';
                        el.style.transition = 'all 0.3s ease';
                    }""", element)

                    await page.wait_for_timeout(random.randint(600, 1000))

                    lib_id = None
                    try:
                        lib_el = await element.query_selector('span:has-text("Library ID")')
                        if not lib_el:
                            lib_el = await element.query_selector('div:has-text("Library ID")')
                        if lib_el:
                            lib_text = await lib_el.inner_text()
                            match = re.search(r'Library ID[:\s]+(\d+)', lib_text)
                            if match:
                                lib_id = match.group(1)
                    except Exception:
                        pass

                    page_name = 'Unknown'
                    _PAGE_NOISE = [
                        'sponsored', 'active', 'inactive', 'ad library',
                        'see ad details', 'see summary', 'about this ad',
                        'all platforms', 'facebook', 'instagram', 'messenger',
                        'audience network', 'started running', 'run on',
                        'library id', 'platforms', 'impressions',
                        'eu transparency', 'multiple versions',
                        'previous items', 'next items', 'see all',
                        'learn more', 'shop now', 'sign up', 'send message',
                        'play.google.com', 'disclaimer',
                        'drop-down', 'drop down', 'open drop', 'close drop',
                        'toggle', 'expand', 'collapse', 'menu', 'carousel',
                    ]

                    def _is_noise(txt: str) -> bool:
                        """Return True if txt matches any noise substring."""
                        low = txt.lower()
                        return any(n in low for n in _PAGE_NOISE)

                    # --- Priority 1: anchor with facebook.com href ---
                    try:
                        link_els = await element.query_selector_all('a[href*="facebook.com"]')
                        for link_el in link_els:
                            pn = (await link_el.inner_text()).strip()
                            if (
                                pn
                                and 3 <= len(pn) <= 60
                                and '\n' not in pn
                                and not pn.isdigit()
                                and not _is_noise(pn)
                            ):
                                page_name = pn
                                break
                    except Exception:
                        pass

                    # --- Priority 2: element with aria-label ---
                    if page_name == 'Unknown':
                        try:
                            aria_el = await element.query_selector('[aria-label]')
                            if aria_el:
                                aria_val = await aria_el.get_attribute('aria-label')
                                if (
                                    aria_val
                                    and 3 <= len(aria_val.strip()) <= 60
                                    and not _is_noise(aria_val.strip())
                                ):
                                    page_name = aria_val.strip()
                        except Exception:
                            pass

                    # --- Priority 3: short div/span text before ad body ---
                    if page_name == 'Unknown':
                        try:
                            header_els = await element.query_selector_all('div, span')
                            for hel in header_els:
                                htxt = (await hel.inner_text()).strip()
                                if (
                                    htxt
                                    and 3 <= len(htxt) <= 60
                                    and '\n' not in htxt
                                    and not htxt.isdigit()
                                    and not _is_noise(htxt)
                                    and not re.match(r'^\d{1,2}\s+\w+\s+\d{4}', htxt)
                                ):
                                    page_name = htxt
                                    break
                        except Exception:
                            pass


                    days_active = 1
                    date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', raw_text)
                    if date_match:
                        try:
                            start_date = datetime.strptime(date_match.group(1), '%d %B %Y')
                            days_active = (datetime.now() - start_date).days
                            days_active = max(1, days_active)
                        except ValueError:
                            try:
                                start_date = datetime.strptime(date_match.group(1), '%d %b %Y')
                                days_active = (datetime.now() - start_date).days
                                days_active = max(1, days_active)
                            except ValueError:
                                pass

                    await page.evaluate("""el => {
                        el.style.outline = '';
                        el.style.boxShadow = '';
                    }""", element)

                    ad_copy = text.encode('utf-8', errors='replace').decode('utf-8')
                    ad_id = lib_id if lib_id else f"fb_{abs(hash(ad_copy[:50]))}"

                    results.append(RawAdRecord(
                        ad_id=ad_id,
                        page_name=page_name,
                        ad_copy=ad_copy,
                        industry=industry,
                        source_type="playwright_scrape",
                        days_active=days_active,
                    ))
                    processed += 1
                    logger.info(f"Card {processed}: page='{page_name}', id={ad_id}, days={days_active}")

                    await page.wait_for_timeout(random.randint(200, 400))

                except Exception as e:
                    logger.debug(f"Card extraction error: {e}")
                    continue

            logger.info(f"Extracted {processed} ads total. Skipped {skipped_duplicates} duplicates.")

            # FIX 8: persist storage state after a successful scrape
            if results:
                try:
                    _BROWSER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(_BROWSER_STATE_PATH))
                    logger.info(f"Browser state saved to {_BROWSER_STATE_PATH}.")
                except Exception as e:
                    logger.warning(f"Could not save browser state: {e}")

            await browser.close()

    except Exception as e:
        logger.error(f"Error scraping Facebook ads: {e}")
        return []

    if results:
        from src.db.watchlist import check_and_update_watchlist
        check_and_update_watchlist(results)

    return results


def scrape_ads_sync(industry: str, max_ads: int = 100) -> List[RawAdRecord]:
    """Synchronous wrapper that runs the async scraper via asyncio.run()."""
    from src.core.relevance import filter_by_relevance
    results = asyncio.run(scrape_facebook_ads(industry, max_ads))
    results = filter_by_relevance(results, industry)

    # ML relevance filter + feedback logging
    try:
        from src.ml.relevance_classifier import RelevanceClassifier
        rc = RelevanceClassifier()
        kept, filtered_out = rc.filter_relevant(results, industry)
        for ad in kept:
            rc.log_feedback(ad.ad_id, industry, was_relevant=True, ad_copy=ad.ad_copy)
        for ad in filtered_out:
            rc.log_feedback(ad.ad_id, industry, was_relevant=False, ad_copy=ad.ad_copy)
        logger.info(
            "ML filter: %d kept, %d filtered out for industry '%s'",
            len(kept), len(filtered_out), industry,
        )
        return kept
    except Exception as e:
        logger.warning("ML relevance filter unavailable, returning keyword-filtered results: %s", e)
        return results
