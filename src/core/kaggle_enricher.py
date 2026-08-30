"""
AdLens PK — Kaggle E-Commerce Demand Enricher
Integrates Pakistan's Largest Ecommerce Dataset from Kaggle to enrich
ad intelligence with real-world consumer order volume and category demand benchmarks.

Kaggle Dataset Slug: zusmani/pakistans-largest-ecommerce-dataset
"""

import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Union
import pandas as pd

logger = logging.getLogger(__name__)

# Kaggle Dataset Identifier
KAGGLE_DATASET_SLUG = "zusmani/pakistans-largest-ecommerce-dataset"

# Base directory for Kaggle dataset storage (src/data/kaggle)
KAGGLE_DIR = Path(__file__).resolve().parent.parent / "data" / "kaggle"

# Download instruction command
DOWNLOAD_COMMAND = f"kaggle datasets download -d {KAGGLE_DATASET_SLUG} -p src/data/kaggle --unzip"

# Missing dataset message
MISSING_DATA_MESSAGE = "Kaggle data not loaded — run download command"

# In-memory cache for parsed category demand
_CACHED_DEMAND: Optional[Dict[str, int]] = None

# Industry keyword to Kaggle category taxonomy mapping
INDUSTRY_CATEGORY_MAP: Dict[str, List[str]] = {
    "fashion": ["Women's Fashion", "Men's Fashion"],
    "clothing": ["Women's Fashion", "Men's Fashion"],
    "apparel": ["Women's Fashion", "Men's Fashion"],
    "electronics": ["Mobiles & Tablets", "Computing & Tech", "Appliances"],
    "mobile": ["Mobiles & Tablets"],
    "tech": ["Computing & Tech", "Mobiles & Tablets"],
    "beauty": ["Beauty & Grooming"],
    "health": ["Beauty & Grooming", "Superstore"],
    "skincare": ["Beauty & Grooming"],
    "groceries": ["Superstore", "Superstore & Groceries"],
    "superstore": ["Superstore", "Superstore & Groceries"],
    "food": ["Superstore", "Soghaat"],
    "soghaat": ["Soghaat"],
    "home": ["Home & Living"],
    "appliances": ["Appliances"],
    "entertainment": ["Entertainment"],
}


def find_kaggle_csv(directory: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """
    Checks if the target directory contains a CSV dataset file.
    Returns the Path to the first CSV found, or None if no CSV exists.
    """
    search_dir = Path(directory) if directory else KAGGLE_DIR
    if not search_dir.exists() or not search_dir.is_dir():
        return None

    csv_files = sorted(search_dir.glob("*.csv"))
    if csv_files:
        return csv_files[0]
    return None


def print_download_instructions() -> None:
    """Prints clear instructions on how to download the Kaggle dataset."""
    instruction = (
        "\n" + "=" * 70 + "\n"
        "[AdLens PK] Kaggle E-Commerce Dataset not found.\n"
        "To load real Pakistani e-commerce demand benchmarks, run:\n\n"
        f"  {DOWNLOAD_COMMAND}\n\n"
        f"Target directory: {KAGGLE_DIR}\n"
        + "=" * 70 + "\n"
    )
    print(instruction)
    logger.warning("Kaggle dataset missing. Download command: %s", DOWNLOAD_COMMAND)


def _has_kaggle_credentials() -> bool:
    """Checks if Kaggle API credentials exist in environment or ~/.kaggle/kaggle.json."""
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    creds_file = Path.home() / ".kaggle" / "kaggle.json"
    return creds_file.exists()


def download_kaggle_dataset(target_dir: Optional[Union[str, Path]] = None) -> bool:
    """
    Attempts to download the 'Pakistan's Largest Ecommerce Dataset' from Kaggle
    using the Kaggle CLI:
      kaggle datasets download -d zusmani/pakistans-largest-ecommerce-dataset -p src/data/kaggle --unzip
    Returns True if successfully downloaded/extracted, False otherwise.
    """
    out_dir = Path(target_dir) if target_dir else KAGGLE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # If CSV already exists, no download required
    existing_csv = find_kaggle_csv(out_dir)
    if existing_csv:
        logger.info("Kaggle dataset already exists at %s", existing_csv)
        return True

    if not _has_kaggle_credentials():
        logger.warning(
            "Kaggle API credentials not found. Run '%s' manually after setting up Kaggle CLI.",
            DOWNLOAD_COMMAND,
        )
        print_download_instructions()
        return False

    try:
        logger.info("Executing: %s", DOWNLOAD_COMMAND)
        cmd = [
            "kaggle",
            "datasets",
            "download",
            "-d",
            KAGGLE_DATASET_SLUG,
            "-p",
            str(out_dir),
            "--unzip",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode == 0:
            logger.info("Successfully downloaded and extracted Kaggle dataset.")
            return True
        else:
            logger.warning("Kaggle CLI download failed (code %s): %s", res.returncode, res.stderr or res.stdout)
    except Exception as exc:
        logger.warning("Failed to execute Kaggle dataset download: %s", exc)

    # Check if a zip file was downloaded and unzip if needed
    for zip_p in out_dir.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_p, "r") as zip_ref:
                zip_ref.extractall(out_dir)
            return True
        except Exception as e:
            logger.warning("Could not unzip %s: %s", zip_p, e)

    return False


def load_kaggle_demand(
    csv_path: Optional[Union[str, Path]] = None,
    reload: bool = False,
) -> Optional[Dict[str, int]]:
    """
    Reads the Kaggle dataset CSV, finds the category column, and returns real top 10
    category counts as a dict {category_name: order_count}.

    If the CSV file does not exist in src/data/kaggle/, prints download instructions
    and gracefully returns None. Never returns hardcoded fake numbers.
    """
    global _CACHED_DEMAND

    # Return cached demand if available and reload is not requested
    if not reload and _CACHED_DEMAND is not None and csv_path is None:
        return dict(_CACHED_DEMAND)

    if csv_path:
        p = Path(csv_path)
        if p.is_file():
            target_csv = p
        elif p.is_dir():
            target_csv = find_kaggle_csv(p)
        else:
            target_csv = None
    else:
        target_csv = find_kaggle_csv(KAGGLE_DIR)

    # If no CSV file is found, print instructions and return None
    if not target_csv or not target_csv.exists():
        print_download_instructions()
        return None

    try:
        # 1. Read header to detect category column
        header_df = pd.read_csv(target_csv, nrows=0)
        columns = list(header_df.columns)

        candidate_cols = [
            "category_name_1",
            "Category",
            "category_name",
            "category",
            "product_category",
            "item_category",
        ]

        cat_col: Optional[str] = None
        for col in candidate_cols:
            if col in columns:
                cat_col = col
                break

        # Fallback case-insensitive search
        if not cat_col:
            for col in columns:
                if "category" in col.lower() or "cat" in col.lower():
                    cat_col = col
                    break

        if not cat_col:
            logger.warning("No recognized category column found in %s.", target_csv)
            return None

        # 2. Read only the category column for maximum performance
        df = pd.read_csv(target_csv, usecols=[cat_col], low_memory=False)

        # 3. Clean and calculate top 10 categories
        series = (
            df[cat_col]
            .dropna()
            .astype(str)
            .str.strip()
            .loc[lambda s: ~s.str.lower().isin(["\\n", "nan", "none", "unknown", ""])]
        )

        top_10 = series.value_counts().head(10).to_dict()
        result = {str(k): int(v) for k, v in top_10.items() if int(v) > 0}

        if not result:
            logger.warning("No valid category counts found in %s.", target_csv)
            return None

        _CACHED_DEMAND = result
        return dict(result)

    except Exception as exc:
        logger.warning("Error reading Kaggle dataset CSV (%s): %s", target_csv, exc)
        return None


def get_demand_context(
    industry: Optional[str] = None,
    csv_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Takes an industry string and returns a plain English sentence describing
    demand for that industry based on the Kaggle data.

    If the Kaggle CSV is missing, returns "Kaggle data not loaded — run download command"
    rather than fake statistics.
    """
    demand = load_kaggle_demand(csv_path=csv_path)
    if not demand:
        return MISSING_DATA_MESSAGE

    if not industry:
        industry = "general"

    ind_lower = industry.strip().lower()
    sorted_categories = sorted(demand.items(), key=lambda x: x[1], reverse=True)
    total_ecommerce_orders = sum(demand.values())

    # 1. Digital service or non-retail verticals
    if any(k in ind_lower for k in ["edtech", "education", "course", "bootcamp", "training"]):
        return (
            f"Education & Digital Learning operates alongside Pakistan's high-demand "
            f"e-commerce sector ({total_ecommerce_orders:,}+ tracked category orders)."
        )
    if any(k in ind_lower for k in ["marketing", "agency", "b2b", "advertising"]):
        return (
            f"Performance Marketing fuels digital commerce across Pakistan's top categories "
            f"representing {total_ecommerce_orders:,}+ orders in this dataset."
        )
    if any(k in ind_lower for k in ["real estate", "property", "plots", "housing"]):
        return (
            f"Real Estate generates high-ticket commercial demand alongside "
            f"{total_ecommerce_orders:,}+ tracked consumer e-commerce orders in this dataset."
        )

    # 2. Fashion aggregation (Women's Fashion + Men's Fashion if present)
    if "fashion" in ind_lower or "apparel" in ind_lower or "clothing" in ind_lower:
        fashion_total = demand.get("Women's Fashion", 0) + demand.get("Men's Fashion", 0)
        if fashion_total > 0:
            return (
                f"Fashion sees {fashion_total:,}+ orders in this dataset, "
                "making it a leading category in Pakistani e-commerce."
            )

    # 3. Direct or partial matching with category names
    for rank, (cat_name, count) in enumerate(sorted_categories, start=1):
        if ind_lower in cat_name.lower() or cat_name.lower() in ind_lower:
            rank_desc = "the top category" if rank == 1 else f"the #{rank} category"
            return f"{cat_name} sees {count:,}+ orders in this dataset, making it {rank_desc}."

    # 4. Keyword taxonomy mapping
    for keyword, matched_cats in INDUSTRY_CATEGORY_MAP.items():
        if keyword in ind_lower.split() or keyword == ind_lower:
            matched_in_demand = [c for c in matched_cats if c in demand]
            if matched_in_demand:
                total_orders = sum(demand[c] for c in matched_in_demand)
                best_rank = min(
                    (rank for rank, (c, _) in enumerate(sorted_categories, start=1) if c in matched_in_demand),
                    default=len(sorted_categories),
                )
                rank_desc = "the top category" if best_rank == 1 else f"the #{best_rank} category"
                return f"{industry.title()} sees {total_orders:,}+ orders in this dataset, making it {rank_desc}."

    # 5. Default dynamic summary from top category
    top_cat, top_count = sorted_categories[0]
    return (
        f"{industry.title()} operates in a dynamic Pakistani digital market where "
        f"{top_cat} leads with {top_count:,}+ orders in this dataset."
    )
