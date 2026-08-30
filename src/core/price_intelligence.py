import csv
import os
import re
import statistics
from typing import List

from src.core.schemas import RawAdRecord

# PKR price bands definition
_PRICE_BANDS = [
    ("Budget (under Rs.500)",       0,      500),
    ("Economy (Rs.500–1,500)",      500,    1500),
    ("Mid-range (Rs.1,500–3,000)",  1500,   3000),
    ("Upper-mid (Rs.3,000–7,000)",  3000,   7000),
    ("Premium (Rs.7,000–15,000)",   7000,   15000),
    ("Luxury (above Rs.15,000)",    15000,  float("inf")),
]

# Price columns recognised in Kaggle CSVs
_KAGGLE_PRICE_COLS = {"price", "Price", "unit_price", "selling_price"}


def extract_all_prices(ads: List[RawAdRecord]) -> List[float]:
    """
    Extracts all PKR prices from ad_copy fields.
    Handles: Rs. 1,499 / Rs 1499 / PKR 2,000 / rs.999 etc.
    Returns a flat list of floats (one per price occurrence).
    """
    pattern = re.compile(
        r"(?:rs\.?\s*|pkr\s*)([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    prices: List[float] = []
    for ad in ads:
        for match in pattern.finditer(ad.ad_copy):
            raw = match.group(1).replace(",", "")
            try:
                prices.append(float(raw))
            except ValueError:
                pass
    return prices


def compute_price_bands(prices: List[float]) -> dict:
    """
    Returns summary statistics and band breakdown for a list of PKR prices.
    """
    if not prices:
        return {
            "min_price": 0.0,
            "max_price": 0.0,
            "median_price": 0.0,
            "mean_price": 0.0,
            "price_bands": [
                {"label": label, "count": 0, "percentage": 0.0}
                for label, _, _ in _PRICE_BANDS
            ],
        }

    total = len(prices)
    bands = []
    for label, low, high in _PRICE_BANDS:
        count = sum(1 for p in prices if low <= p < high)
        bands.append({
            "label": label,
            "count": count,
            "percentage": round(count / total * 100, 1),
        })

    return {
        "min_price": round(min(prices), 2),
        "max_price": round(max(prices), 2),
        "median_price": round(statistics.median(prices), 2),
        "mean_price": round(statistics.mean(prices), 2),
        "price_bands": bands,
    }


def get_price_positioning(your_price: float, industry_prices: List[float]) -> dict:
    """
    Returns positioning of your_price relative to a list of competitor prices.
    percentile: % of industry_prices strictly cheaper than your_price.
    positioning_label: "Premium" (top 25%), "Mid-range" (25–75%), "Budget" (bottom 25%).
    competitive_count: ads whose price is within ±20% of your_price.
    """
    if not industry_prices:
        return {
            "percentile": 0.0,
            "positioning_label": "Mid-range",
            "competitive_count": 0,
        }

    cheaper = sum(1 for p in industry_prices if p < your_price)
    percentile = round(cheaper / len(industry_prices) * 100, 1)

    if percentile >= 75:
        label = "Premium"
    elif percentile >= 25:
        label = "Mid-range"
    else:
        label = "Budget"

    lower = your_price * 0.80
    upper = your_price * 1.20
    competitive_count = sum(1 for p in industry_prices if lower <= p <= upper)

    return {
        "percentile": percentile,
        "positioning_label": label,
        "competitive_count": competitive_count,
    }


def load_kaggle_price_data(max_rows_per_file: int = 50_000) -> List[float]:
    """
    Reads all Kaggle CSVs in src/data/kaggle/ that contain a recognised
    price column (price, Price, unit_price, selling_price) and returns
    all numeric values found across those files.
    Capped at max_rows_per_file per CSV for fast UI loading.
    """
    kaggle_dir = os.path.join(
        os.path.dirname(__file__), "..", "data", "kaggle"
    )
    kaggle_dir = os.path.normpath(kaggle_dir)
    prices: List[float] = []

    if not os.path.isdir(kaggle_dir):
        return prices

    for fname in os.listdir(kaggle_dir):
        if not fname.lower().endswith(".csv"):
            continue
        path = os.path.join(kaggle_dir, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    continue
                col = next(
                    (c for c in reader.fieldnames if c in _KAGGLE_PRICE_COLS),
                    None,
                )
                if col is None:
                    continue
                rows_read = 0
                for row in reader:
                    if rows_read >= max_rows_per_file:
                        break
                    raw = row.get(col, "").strip().replace(",", "")
                    try:
                        val = float(raw)
                        if val > 0:
                            prices.append(val)
                    except ValueError:
                        pass
                    rows_read += 1
        except Exception:
            pass

    return prices
