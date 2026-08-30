import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.core.scraper import scrape_ads_sync
from src.db.repository import save_ads, init_db, get_all_ads

init_db()

SEARCH_MAP = {
    "fashion": ["sale Pakistan", "dress collection", "fashion pk", "lawn suits"],
    "electronics": ["mobile phone pk", "Samsung Pakistan", "laptop sale"],  
    "health": ["skin care pk", "weight loss Pakistan", "health supplement"],
    "food": ["food delivery pk", "biryani", "restaurant Karachi"],
    "real_estate": ["plot for sale Lahore", "DHA property", "bahria town"],
    "education": ["online course Pakistan", "freelancing", "digital marketing course"],
    "home": ["furniture sale pk", "home decor Pakistan"],
    "general": ["COD Pakistan", "free delivery pk", "sale offer"]
}

summary = []

for industry, terms in SEARCH_MAP.items():
    try:
        print(f"\n{'='*50}")
        print(f"  SCANNING: {industry.upper()}")
        print(f"{'='*50}")

        all_industry_ads = []
        unique_ad_ids = set()

        for term in terms:
            print(f"    -> Term: {term}")
            ads = scrape_ads_sync(industry=term, max_ads=75)
            for ad in ads:
                ad.industry = industry
                if ad.ad_id not in unique_ad_ids:
                    unique_ad_ids.add(ad.ad_id)
                    all_industry_ads.append(ad)
        
        print(f"\n{industry}: {len(all_industry_ads)} unique records returned across terms")

        for r in all_industry_ads:
            print(f"  [{r.days_active}d] {r.page_name[:40]}")

        saved = save_ads(all_industry_ads)
        print(f"{industry}: {saved} saved to DB")

        summary.append({
            "industry": industry,
            "ads_scraped": len(all_industry_ads),
            "ads_saved_new": saved
        })

        if industry != list(SEARCH_MAP.keys())[-1]:
            print("Waiting 15 seconds...")
            time.sleep(15)
    except Exception as e:
        print(f"Error processing {industry}: {e}")
        summary.append({
            "industry": industry,
            "ads_scraped": 0,
            "ads_saved_new": 0
        })

print(f"\n{'='*50}")
print(f"  COLLECTION SUMMARY")
print(f"{'='*50}")
print(f"{'Industry':<20} {'Scraped':<12} {'Saved New':<12}")
print(f"{'-'*20} {'-'*12} {'-'*12}")
for row in summary:
    print(f"{row['industry']:<20} {row['ads_scraped']:<12} {row['ads_saved_new']:<12}")

all_ads = get_all_ads()
print(f"\nTotal ads in database: {len(all_ads)}")
