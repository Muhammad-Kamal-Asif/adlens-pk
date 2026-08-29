"""
AdLens PK — Standalone Database Test Script
Tests SQLite persistence: initializing schema, fetching seed ads, saving to database, and reading back.
"""
import os
import sys

# Ensure UTF-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.db.repository import init_db, save_ads, get_all_ads
from src.core.fetcher import fetch_ads


def main():
    print("=" * 60)
    print("AdLens PK — Database Persistence Test")
    print("=" * 60)

    # 1. Initialize database tables
    print("[1] Initializing database tables via init_db()...")
    init_db()
    print("    [+] Tables initialized successfully.")

    # 2. Fetch mock ads for industry='general'
    print("\n[2] Fetching ads with industry='general' and use_mock=True...")
    records = fetch_ads(industry="general", use_mock=True)
    print(f"    [+] Fetched {len(records)} records from seed dataset.")

    # 3. Save records to DB
    print("\n[3] Saving records to database via save_ads()...")
    saved_count = save_ads(records)
    print(f"    [+] Processed/Saved {saved_count} records to database.")

    # 4. Get all ads from DB and print count
    print("\n[4] Querying records from database via get_all_ads()...")
    all_ads = get_all_ads()
    print("=" * 60)
    print(f"Total count of records saved: {len(all_ads)}")
    print("=" * 60)

    # Preview sample record from DB
    if all_ads:
        first = all_ads[0]
        print(f"\nSample DB Record: ID='{first.ad_id}', Page='{first.page_name}', Industry='{first.industry}'")


if __name__ == "__main__":
    main()
