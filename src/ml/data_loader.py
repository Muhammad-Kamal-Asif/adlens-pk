import pandas as pd
import logging
from pathlib import Path
from src.db.repository import get_all_ads

logger = logging.getLogger(__name__)

def load_training_data() -> pd.DataFrame:
    """
    Reads records from AdLens SQLite DB and Kaggle CSVs.
    Standardizes into a single DataFrame.
    """
    # 1. Read from AdLens database
    db_records = get_all_ads()
    db_rows = []
    
    for r in db_records:
        # get_all_ads returns list of dicts. We map them safely.
        db_rows.append({
            "ad_copy": r.get("ad_copy", ""),
            "days_active": r.get("days_active", 1),
            "industry": r.get("industry", "general"),
            "has_cod": bool(r.get("has_cod", False)),
            "has_price": bool(r.get("price_mentioned", False) or r.get("has_price", False)),
            "cta_type": r.get("primary_cta", r.get("cta_raw", "unknown")),
            "clicked": pd.NA,
            "source": "database"
        })
        
    db_df = pd.DataFrame(db_rows)
    db_count = len(db_df)
    print(f"Database rows loaded: {db_count}")
    
    # 2. Read every CSV from src/data/kaggle/
    kaggle_dir = Path("src/data/kaggle")
    kaggle_dfs = []
    
    if kaggle_dir.exists() and kaggle_dir.is_dir():
        for csv_path in kaggle_dir.rglob("*.csv"):
            try:
                try:
                    df = pd.read_csv(csv_path, low_memory=False)
                except UnicodeDecodeError:
                    df = pd.read_csv(csv_path, encoding="latin1", low_memory=False)

                # Standardize columns
                mapped_df = pd.DataFrame(index=df.index)

                # Find ad copy text
                if "ad_copy" in df.columns:
                    mapped_df["ad_copy"] = df["ad_copy"]
                elif "text" in df.columns:
                    mapped_df["ad_copy"] = df["text"]
                elif "description" in df.columns:
                    mapped_df["ad_copy"] = df["description"]
                elif "Ad Text" in df.columns:
                    mapped_df["ad_copy"] = df["Ad Text"]
                elif "ad_text" in df.columns:
                    mapped_df["ad_copy"] = df["ad_text"]
                elif "Ad Topic Line" in df.columns:
                    mapped_df["ad_copy"] = df["Ad Topic Line"]
                else:
                    mapped_df["ad_copy"] = ""

                mapped_df["days_active"] = df.get("days_active", -1)
                mapped_df["industry"] = df.get("industry", "general")
                mapped_df["has_cod"] = df.get("has_cod", False)
                mapped_df["has_price"] = df.get("has_price", False)

                if "cta_type" in df.columns:
                    mapped_df["cta_type"] = df["cta_type"]
                elif "cta" in df.columns:
                    mapped_df["cta_type"] = df["cta"]
                else:
                    mapped_df["cta_type"] = "unknown"

                # Capture click/conversion labels when available as a fallback target.
                if "Clicked on Ad" in df.columns:
                    mapped_df["clicked"] = df["Clicked on Ad"]
                elif "Clicked" in df.columns:
                    mapped_df["clicked"] = df["Clicked"]
                else:
                    mapped_df["clicked"] = pd.NA

                mapped_df["source"] = "kaggle"

                # 4. For Kaggle rows that lack days_active, use -1 as placeholder
                mapped_df["days_active"] = mapped_df["days_active"].fillna(-1).astype(int)

                kaggle_dfs.append(mapped_df)
                print(f"Kaggle file '{csv_path.name}' loaded: {len(mapped_df)} rows")
            except Exception as e:
                # catching errors silently per file
                pass
                
    if kaggle_dfs:
        kaggle_combined = pd.concat(kaggle_dfs, ignore_index=True)
    else:
        # Create empty with correct columns if no kaggle files
        kaggle_combined = pd.DataFrame(columns=[
            "ad_copy", "days_active", "industry", "has_cod", "has_price", "cta_type", "clicked", "source"
        ])
        
    # Combine both
    final_df = pd.concat([db_df, kaggle_combined], ignore_index=True)
    
    # 5. Print summary
    print(f"Total combined rows: {len(final_df)}")
    return final_df
