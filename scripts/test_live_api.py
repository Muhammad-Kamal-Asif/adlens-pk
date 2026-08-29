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

from src.core.fetcher import fetch_ads


def main():
    print("=" * 60)
    print("Testing fetch_ads with industry='fashion' and use_mock=False")
    print("=" * 60)

    records = fetch_ads(industry="fashion", use_mock=False)

    print(f"\nTotal records fetched: {len(records)}\n")
    print("=" * 60)
    print("First 3 Records:")
    print("=" * 60)

    for idx, record in enumerate(records[:3], start=1):
        print(f"\n--- Record {idx} ---")
        print(f"Page Name   : {record.page_name}")
        print(f"Source Type : {record.source_type}")
        print(f"Ad Copy (100 chars): {record.ad_copy[:100]}...")


if __name__ == "__main__":
    main()
