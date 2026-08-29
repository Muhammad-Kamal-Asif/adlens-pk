"""
Test script for src/core/kaggle_enricher.py
"""
import os
import sys

# Ensure UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.kaggle_enricher import load_kaggle_demand, get_demand_context


def main():
    print("=" * 60)
    print("Testing Kaggle Enricher Module")
    print("=" * 60)

    # 1. Load top 10 categories
    demand = load_kaggle_demand()
    print(f"\nTop 10 Category Demand Map ({len(demand)} categories):")
    for rank, (cat, count) in enumerate(demand.items(), start=1):
        print(f"  {rank:2d}. {cat:<25} : {count:,} orders")

    # 2. Test get_demand_context for various industries
    test_industries = ["Fashion", "Electronics", "Beauty", "EdTech", "Marketing", "Home Decor", "Real Estate"]
    print("\nDemand Context Descriptions:")
    for ind in test_industries:
        ctx = get_demand_context(ind)
        print(f"\n  [Industry: {ind}]")
        print(f"  -> {ctx}")

    print("\n" + "=" * 60)
    print("Kaggle Enricher Test Completed Successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
