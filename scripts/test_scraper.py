import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import logging

# Add project root to sys.path to allow importing from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

from src.core.scraper import scrape_ads_sync


def main():
    print("Running scraper for industry='fashion', max_ads=20...")
    records = scrape_ads_sync(industry="fashion", max_ads=20)

    print(f"\nTotal records returned: {len(records)}")

    for i, record in enumerate(records[:3]):
        ad_copy_trunc = (
            record.ad_copy[:100] + "..."
            if record.ad_copy and len(record.ad_copy) > 100
            else record.ad_copy
        )
        print(f"--- Record {i+1} ---")
        print(f"Page Name:   {record.page_name}")
        print(f"Days Active: {record.days_active}")
        print(f"Ad Copy:     {ad_copy_trunc}")
        print()


if __name__ == "__main__":
    main()
