import time
import sys
import argparse
import re
from datetime import datetime
from collections import Counter
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core.scraper import scrape_ads_sync
from src.db.repository import save_ads, init_db, get_all_ads

init_db()

SEARCH_MAP = {
    "fashion": ["sale Pakistan", "dress collection", "fashion pk", "lawn suits",
                "Khaadi", "Gul Ahmed", "J. lawn", "Sapphire pk", "Bonanza Satrangi"],
    "electronics": ["mobile phone pk", "Samsung Pakistan", "laptop sale",
                    "Haier Pakistan", "QMobile", "PEL appliances"],
    "health": ["skin care pk", "weight loss Pakistan", "health supplement"],
    "food": ["food delivery pk", "biryani", "restaurant Karachi",
             "Foodpanda Pakistan", "Cheetay", "Yayvo food"],
    "real_estate": ["plot for sale Lahore", "DHA property", "bahria town",
                    "Zameen.com", "Graana", "OLX Pakistan property"],
    "education": ["online course Pakistan", "freelancing", "digital marketing course",
                  "Alison Pakistan", "Digiskills", "NAVTTC"],
    "home": ["furniture sale pk", "home decor Pakistan"],
    "general": ["COD Pakistan", "free delivery pk", "sale offer"]
}

def generate_dynamic_terms(industry: str, limit: int = 5) -> List[str]:
    all_ads = get_all_ads()
    industry_ads = [ad for ad in all_ads if getattr(ad, 'industry', None) == industry]
    
    if not industry_ads:
        return []
        
    page_names = [ad.page_name for ad in industry_ads if getattr(ad, 'page_name', None)]
    
    words = []
    for ad in industry_ads:
        if getattr(ad, 'ad_copy', None):
            tokens = re.findall(r'\b\w{6,}\b', ad.ad_copy.lower())
            words.extend(tokens)
            
    word_counts = Counter(words)
    frequent_words = [word for word, count in word_counts.items() if count > 3]
    
    existing_terms = set(t.lower() for t in SEARCH_MAP.get(industry, []))
    
    new_terms = []
    for term in page_names + frequent_words:
        term_clean = term.strip()
        if term_clean and term_clean.lower() not in existing_terms and term_clean.lower() not in [nt.lower() for nt in new_terms]:
            new_terms.append(term_clean)
            if len(new_terms) >= limit:
                break
                
    return new_terms

def collect_industry(industry, terms):
    start_time = time.time()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting {industry.upper()}")
    all_industry_ads = []
    unique_ad_ids = set()
    
    try:
        dynamic_terms = generate_dynamic_terms(industry, limit=5)
        if dynamic_terms:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Added {len(dynamic_terms)} dynamic terms for {industry.upper()}: {dynamic_terms}")
            terms = list(terms) + dynamic_terms
            SEARCH_MAP[industry].extend(dynamic_terms)

        for term in terms:
            print(f"[{industry.upper()}]   -> Term: {term}")
            ads = scrape_ads_sync(industry=term, max_ads=75)
            for ad in ads:
                ad.industry = industry
                if ad.ad_id not in unique_ad_ids:
                    unique_ad_ids.add(ad.ad_id)
                    all_industry_ads.append(ad)
        
        saved = save_ads(all_industry_ads)
        scraped = len(all_industry_ads)
        elapsed = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Completed {industry.upper()} — {scraped} scraped, {saved} saved ({elapsed:.0f}s)")
        
        return {
            "industry": industry,
            "ads_scraped": scraped,
            "ads_saved_new": saved
        }
    except Exception as e:
        print(f"[{industry.upper()}] Error processing {industry}: {e}")
        return {
            "industry": industry,
            "ads_scraped": 0,
            "ads_saved_new": 0
        }

def run_collection(parallel: bool):
    batch_start = time.time()
    print(f"\nBatch started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary = []
    
    if parallel:
        print("\n=== RUNNING IN PARALLEL MODE (4 WORKERS) ===")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(collect_industry, ind, terms): ind for ind, terms in SEARCH_MAP.items()}
            for future in as_completed(futures):
                ind = futures[future]
                try:
                    res = future.result()
                    summary.append(res)
                except Exception as e:
                    print(f"Error in future for {ind}: {e}")
    else:
        print("\n=== RUNNING IN SEQUENTIAL MODE ===")
        for ind, terms in SEARCH_MAP.items():
            res = collect_industry(ind, terms)
            summary.append(res)
            
            # Wait between sequential runs
            if ind != list(SEARCH_MAP.keys())[-1]:
                print(f"Waiting 15 seconds before next industry...")
                time.sleep(15)
                
    print(f"\n{'='*50}")
    print(f"  COLLECTION SUMMARY")
    print(f"{'='*50}")
    print(f"{'Industry':<20} {'Scraped':<12} {'Saved New':<12}")
    print(f"{'-'*20} {'-'*12} {'-'*12}")
    for row in summary:
        print(f"{row['industry']:<20} {row['ads_scraped']:<12} {row['ads_saved_new']:<12}")

    all_ads = get_all_ads()
    print(f"\nTotal ads in database: {len(all_ads)}")
    
    batch_elapsed = time.time() - batch_start
    print(f"Batch completed in {batch_elapsed:.0f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Collect Ads")
    parser.add_argument("--parallel", action="store_true", help="Run industries in parallel using ThreadPoolExecutor")
    parser.add_argument("--continuous", action="store_true", help="Run continuously in a loop")
    args = parser.parse_args()
    
    if args.continuous:
        while True:
            print(f"\n\n*** STARTING CONTINUOUS BATCH ***")
            run_collection(args.parallel)
            print("\nWaiting 1 hour before next batch...")
            time.sleep(3600)
    else:
        run_collection(args.parallel)
