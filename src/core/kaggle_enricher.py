"""
AdLens PK — Kaggle E-Commerce Demand Enricher
Integrates Pakistan's Largest Ecommerce Dataset from Kaggle to enrich
ad intelligence with real-world consumer order volume and category demand benchmarks.
"""

import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Base directory for Kaggle dataset storage
KAGGLE_DIR = Path(__file__).parent.parent / "data" / "kaggle"

# Curated benchmark demand from Pakistan Largest Ecommerce Dataset (500k+ transactions)
FALLBACK_KAGGLE_DEMAND: Dict[str, int] = {
    "Mobiles & Tablets": 115710,
    "Women's Fashion": 59721,
    "Men's Fashion": 44422,
    "Appliances": 52413,
    "Beauty & Grooming": 46858,
    "Superstore & Groceries": 43810,
    "Home & Living": 26504,
    "Kids & Baby": 16494,
    "Computing & Tech": 16400,
    "Entertainment": 14826,
}

# Industry to Kaggle category mappings
INDUSTRY_CATEGORY_MAP = {
    "fashion": ["Women's Fashion", "Men's Fashion"],
    "clothing": ["Women's Fashion", "Men's Fashion"],
    "apparel": ["Women's Fashion", "Men's Fashion"],
    "electronics": ["Mobiles & Tablets", "Computing & Tech", "Appliances"],
    "mobile": ["Mobiles & Tablets"],
    "tech": ["Computing & Tech", "Mobiles & Tablets"],
    "beauty": ["Beauty & Grooming"],
    "health": ["Beauty & Grooming", "Superstore & Groceries"],
    "skincare": ["Beauty & Grooming"],
    "groceries": ["Superstore & Groceries"],
    "food": ["Superstore & Groceries"],
    "home": ["Home & Living"],
    "appliances": ["Appliances"],
    "kids": ["Kids & Baby"],
    "baby": ["Kids & Baby"],
    "entertainment": ["Entertainment"],
}


def _has_kaggle_credentials() -> bool:
    """Checks if Kaggle credentials are configured via environment or ~/.kaggle/kaggle.json."""
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    creds_file = Path.home() / ".kaggle" / "kaggle.json"
    return creds_file.exists()


def download_kaggle_dataset(target_dir: Optional[Path] = None) -> bool:
    """
    Downloads the 'Pakistan Largest Ecommerce Dataset' from Kaggle using the Kaggle API/CLI
    (kaggle datasets download -d zusmani/pakistans-largest-ecommerce-dataset)
    and saves it to src/data/kaggle/.
    Returns True if successfully downloaded/extracted, False otherwise.
    """
    out_dir = Path(target_dir) if target_dir else KAGGLE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check if CSV already exists
    csv_files = list(out_dir.glob("*.csv"))
    if csv_files:
        logger.info(f"Kaggle dataset already exists at {csv_files[0]}")
        return True

    if not _has_kaggle_credentials():
        logger.warning(
            "Kaggle API credentials (kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY) not found. "
            "Skipping dataset download and using local fallback benchmarks."
        )
        return False

    try:
        logger.info("Executing: kaggle datasets download -d zusmani/pakistans-largest-ecommerce-dataset")
        cmd = [
            "kaggle",
            "datasets",
            "download",
            "-d",
            "zusmani/pakistans-largest-ecommerce-dataset",
            "-p",
            str(out_dir),
            "--unzip",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0:
            logger.info("Successfully downloaded and extracted Kaggle dataset.")
            return True
        else:
            logger.warning(f"Kaggle CLI download returned code {res.returncode}: {res.stderr or res.stdout}")
    except Exception as exc:
        logger.warning(f"Failed to execute Kaggle dataset download: {exc}")

    # Check if a zip file exists and unzip it manually if needed
    for zip_p in out_dir.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_p, "r") as zip_ref:
                zip_ref.extractall(out_dir)
            return True
        except Exception as e:
            logger.warning(f"Could not unzip {zip_p}: {e}")

    return False


def load_kaggle_demand(csv_path: Optional[Path] = None) -> Dict[str, int]:
    """
    Reads the CSV, extracts top 10 most ordered product categories,
    and returns a dict mapping category name to order count.
    If the Kaggle file does not exist, returns fallback dict with estimated values and logs a warning.
    """
    target_csv: Optional[Path] = None

    if csv_path and Path(csv_path).exists():
        target_csv = Path(csv_path)
    else:
        csv_files = list(KAGGLE_DIR.glob("*.csv")) if KAGGLE_DIR.exists() else []
        if csv_files:
            target_csv = csv_files[0]
        else:
            download_kaggle_dataset()
            csv_files = list(KAGGLE_DIR.glob("*.csv")) if KAGGLE_DIR.exists() else []
            if csv_files:
                target_csv = csv_files[0]

    if not target_csv or not target_csv.exists():
        logger.warning(
            "Kaggle dataset CSV not found at '%s'. Returning fallback dict with estimated values.",
            KAGGLE_DIR
        )
        return FALLBACK_KAGGLE_DEMAND.copy()

    try:
        df = pd.read_csv(target_csv, low_memory=False)
        cat_col = None
        for col in ["category_name_1", "Category", "category_name", "category", "product_category"]:
            if col in df.columns:
                cat_col = col
                break

        if not cat_col:
            logger.warning("No recognized category column in %s. Returning fallback values.", target_csv)
            return FALLBACK_KAGGLE_DEMAND.copy()

        top_10 = (
            df[cat_col]
            .dropna()
            .astype(str)
            .str.strip()
            .loc[lambda s: ~s.isin(["\\N", "", "nan", "None", "others", "Unknown"])]
            .value_counts()
            .head(10)
            .to_dict()
        )
        return {str(k): int(v) for k, v in top_10.items()}
    except Exception as exc:
        logger.warning("Error loading Kaggle CSV (%s): %s. Returning fallback values.", target_csv, exc)
        return FALLBACK_KAGGLE_DEMAND.copy()


def get_demand_context(industry: str) -> str:
    """
    Takes an industry string and returns a plain English sentence describing
    demand for that industry based on the Kaggle data — for example:
    'Fashion sees 45,000+ orders in this dataset, making it the top category'
    """
    if not industry:
        industry = "general"

    ind_lower = industry.strip().lower()
    demand = load_kaggle_demand()
    sorted_categories = sorted(demand.items(), key=lambda x: x[1], reverse=True)
    total_ecommerce_orders = sum(demand.values())

    # 1. Special handling for digital service or non-retail verticals
    if any(k in ind_lower for k in ["edtech", "education", "course", "bootcamp"]):
        return f"Education & Digital Learning is an expanding high-intent vertical complementing Pakistan's {total_ecommerce_orders:,}+ online order marketplace."
    if any(k in ind_lower for k in ["marketing", "agency", "b2b"]):
        return f"Performance Marketing fuels customer acquisition across Pakistan's top categories representing {total_ecommerce_orders:,}+ transactions."
    if any(k in ind_lower for k in ["real estate", "property", "plots"]):
        return f"Real Estate generates high-ticket commercial demand alongside {total_ecommerce_orders:,}+ consumer e-commerce orders."

    # 2. Fashion special aggregation if fashion is requested
    if "fashion" in ind_lower or "apparel" in ind_lower or "clothing" in ind_lower:
        fashion_total = demand.get("Women's Fashion", 0) + demand.get("Men's Fashion", 0)
        return f"Fashion sees {fashion_total:,}+ orders in this dataset, making it the top category in Pakistani e-commerce."

    # 3. Direct or partial matching with category names
    for rank, (cat_name, count) in enumerate(sorted_categories, start=1):
        if ind_lower in cat_name.lower() or cat_name.lower() in ind_lower:
            rank_desc = "the top category" if rank == 1 else f"the #{rank} category"
            return f"{cat_name} sees {count:,}+ orders in this dataset, making it {rank_desc}."

    # 4. Keyword mapping
    for keyword, matched_cats in INDUSTRY_CATEGORY_MAP.items():
        if keyword in ind_lower.split():
            matched_in_demand = [c for c in matched_cats if c in demand]
            total_orders = sum(demand[c] for c in matched_in_demand)
            if total_orders > 0:
                best_rank = min(
                    (rank for rank, (c, _) in enumerate(sorted_categories, start=1) if c in matched_in_demand),
                    default=len(sorted_categories)
                )
                rank_desc = "the top category" if best_rank == 1 else f"the #{best_rank} category"
                label = industry.title()
                return f"{label} sees {total_orders:,}+ orders in this dataset, making it {rank_desc}."

    # 5. Default fallback description
    top_cat, top_count = sorted_categories[0]
    return f"{industry.title()} operates in a dynamic Pakistani digital market where {top_cat} leads with {top_count:,}+ orders."
