"""
AdLens PK — Real Kaggle Dataset Integration Test
Tests loading real-world consumer order volume and category demand benchmarks
directly from the Kaggle dataset CSV.
"""

import os
import sys
from pathlib import Path

# Ensure UTF-8 encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.kaggle_enricher import (
    load_kaggle_demand,
    get_demand_context,
    DOWNLOAD_COMMAND,
    KAGGLE_DIR,
)


def main():
    print("=" * 70)
    print("AdLens PK — Testing Real Kaggle Demand Dataset")
    print("=" * 70)

    # 1. Call load_kaggle_demand()
    print("\n[Step 1] Loading Kaggle demand benchmark data...")
    demand = load_kaggle_demand()

    # 2. Check if data is loaded or None
    if demand is None:
        print("\n[Step 2] Kaggle dataset CSV was NOT found!")
        print("Please run the following command to download and extract the dataset:")
        print(f"\n  {DOWNLOAD_COMMAND}\n")
        print(f"Target directory: {KAGGLE_DIR}")
    else:
        # 3. Print top 10 categories with real counts
        print(f"\n[Step 2] Kaggle dataset loaded successfully ({len(demand)} categories):")
        print(f"{'-' * 60}")
        print(f"{'Rank':<6} {'Category':<35} {'Orders':>12}")
        print(f"{'-' * 60}")
        for rank, (cat, count) in enumerate(demand.items(), start=1):
            print(f"{rank:<6} {cat:<35} {count:>12,}")
        print(f"{'-' * 60}")
        total_orders = sum(demand.values())
        print(f"{'Total':<42} {total_orders:>12,}")

    # 4. Call get_demand_context("fashion") and print result
    print("\n[Step 3] Querying demand context for 'fashion'...")
    fashion_context = get_demand_context("fashion")
    print(f"Result:\n  -> \"{fashion_context}\"")

    print("\n" + "=" * 70)
    print("Kaggle Real Test Finished.")
    print("=" * 70)


if __name__ == "__main__":
    main()
