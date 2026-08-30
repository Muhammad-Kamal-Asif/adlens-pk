"""
AdLens PK - Command-Line Interface
Usage:  python -m src.cli.cli <command> [options]
"""

import argparse
import re
import sys
from datetime import datetime
from statistics import mean

import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

# Force UTF-8 output on Windows to avoid charmap codec errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _h(text: str) -> str:
    """Cyan header."""
    return f"{Fore.CYAN}{Style.BRIGHT}{text}{Style.RESET_ALL}"


def _ok(text: str) -> str:
    """Green success line."""
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}"


def _warn(text: str) -> str:
    """Yellow warning line."""
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"


def _err(text: str) -> str:
    """Red error line."""
    return f"{Fore.RED}{text}{Style.RESET_ALL}"


def _kv(key: str, value: str) -> str:
    """Dim-key / bright-value pair."""
    return f"  {Fore.CYAN}{key:<28}{Style.RESET_ALL}{value}"


def _rule(char: str = "-", width: int = 60) -> str:
    return f"{Fore.CYAN}{char * width}{Style.RESET_ALL}"


def _banner(title: str) -> None:
    print(_rule())
    print(_h(f"  {title}"))
    print(_rule())


# ---------------------------------------------------------------------------
# Command: fetch
# ---------------------------------------------------------------------------

def cmd_fetch(args: argparse.Namespace) -> int:
    industry = args.industry.lower()
    live = args.live

    print(_h(f"\nFetching ads - industry: {industry}  mode: {'LIVE' if live else 'DEMO'}"))

    try:
        if live:
            from src.core.scraper import scrape_ads_sync
            ads = scrape_ads_sync(industry=industry, max_ads=args.max_ads)
            if not ads:
                print(_warn("Live scrape returned 0 ads; falling back to demo dataset."))
                from src.core.fetcher import fetch_ads
                ads = fetch_ads(industry=industry, use_mock=True)
        else:
            from src.core.fetcher import fetch_ads
            ads = fetch_ads(industry=industry, use_mock=True)
    except Exception as exc:
        print(_err(f"Fetch failed: {exc}"))
        return 1

    if not ads:
        print(_warn("No ads returned."))
        return 0

    # Save to DB
    try:
        from src.db.repository import save_ads
        saved = save_ads(ads)
        print(_ok(f"Saved {saved} new record(s) to database (skipped {len(ads) - saved} duplicates)."))
    except Exception as exc:
        print(_warn(f"DB save failed: {exc}"))

    _banner(f"Records returned: {len(ads)}")
    for i, ad in enumerate(ads, 1):
        snippet = ad.ad_copy[:80].replace("\n", " ")
        if len(ad.ad_copy) > 80:
            snippet += "..."
        print(f"  {Fore.YELLOW}{i:>3}.{Style.RESET_ALL} {Fore.WHITE}{ad.page_name:<30}{Style.RESET_ALL} {snippet}")

    return 0


# ---------------------------------------------------------------------------
# Command: analyze
# ---------------------------------------------------------------------------

def cmd_analyze(args: argparse.Namespace) -> int:
    industry = args.industry.lower()

    print(_h(f"\nAnalyzing ads for industry: {industry}"))

    from src.db.repository import get_all_ads, init_db
    init_db()
    all_ads_raw = get_all_ads()

    # Case-insensitive industry filter
    matched = [a for a in all_ads_raw if a.get("industry", "").lower() == industry]

    if not matched:
        print(_warn(f"No ads found in DB for industry '{industry}'."))
        print(_warn(f"Available industries: {sorted({a['industry'] for a in all_ads_raw})}"))
        return 0

    from src.core.schemas import RawAdRecord
    from src.core.extractor import build_offer_matrix, get_survivor_ads
    from src.core.classifier import analyze_hooks

    records = [
        RawAdRecord(
            ad_id=a.get("ad_id", ""),
            page_name=a.get("page_name", ""),
            ad_copy=a.get("ad_copy", ""),
            industry=a.get("industry", industry),
            source_type=a.get("source_type", "curated_seed"),
            days_active=a.get("days_active") or 1,
        )
        for a in matched
    ]

    offer_matrix = build_offer_matrix(records)
    hook_report = analyze_hooks(records)
    survivors = get_survivor_ads(records, min_days=30)

    # Avg days active from DB raw data
    days_list = [a.get("days_active") or 1 for a in matched]
    avg_days = round(mean(days_list), 1)

    _banner(f"Offer & Hook Analysis - {industry.title()}")
    print(_kv("Total ads", str(len(records))))
    print(_kv("COD adoption rate", f"{offer_matrix.cod_prevalence_pct:.1f}%"))
    print(_kv("Free delivery rate", f"{offer_matrix.free_shipping_prevalence_pct:.1f}%"))
    print(_kv("Most common CTA", offer_matrix.most_common_cta))
    print(_kv("Dominant language", str(hook_report.dominant_language)))
    print(_kv("Dominant hook type", str(hook_report.dominant_hook_type)))
    print(_kv("Avg days active", str(avg_days)))
    print(_kv("Survivor ads (30+ days)", str(len(survivors))))

    if survivors:
        print(f"\n  {Fore.CYAN}Top survivor ads:{Style.RESET_ALL}")
        for ad in survivors[:5]:
            snippet = ad.ad_copy[:70].replace("\n", " ")
            print(f"    {Fore.GREEN}*{Style.RESET_ALL} {ad.page_name}: {snippet}")

    return 0


# ---------------------------------------------------------------------------
# Command: train
# ---------------------------------------------------------------------------

def cmd_train(_args: argparse.Namespace) -> int:
    print(_h("\nStarting model training (GradientBoostingClassifier - 5-fold CV)..."))
    print(_warn("This may take 30-120 seconds depending on dataset size.\n"))

    try:
        from src.ml.trainer import AdSurvivalTrainer
        trainer = AdSurvivalTrainer()
        result = trainer.run()
    except Exception as exc:
        print(_err(f"Training failed: {exc}"))
        return 1

    if not result.get("success"):
        print(_err(f"Training error: {result.get('error', 'Unknown')}"))
        return 1

    _banner("Training Complete")
    print(_kv("Accuracy (5-fold CV)", f"{result['accuracy']:.4f}  ({result['accuracy']*100:.1f}%)"))
    print(_kv("Records used", str(result.get("records_used", "?"))))
    print(_kv("Duration", f"{result.get('duration_seconds', 0):.1f}s"))
    print(_kv("Model saved to", result.get("model_path", "?")))
    print()
    print(_ok("Model trained and saved successfully."))
    return 0


# ---------------------------------------------------------------------------
# Command: grade
# ---------------------------------------------------------------------------

def cmd_grade(args: argparse.Namespace) -> int:
    ad_copy = args.copy
    industry = args.industry.lower() if args.industry else "general"

    # Simple heuristics for has_cod / mentions_price (no DB lookup needed)
    lower = ad_copy.lower()
    has_cod = bool(re.search(r"\b(cash on delivery|cod|payment on delivery)\b", lower))
    mentions_price = bool(re.search(r"(?:rs\.?|pkr)\s?[0-9,]+", lower))

    print(_h(f"\nGrading ad copy - industry: {industry}"))
    print(f"  {Fore.WHITE}\"{ad_copy[:100]}{'...' if len(ad_copy)>100 else ''}\"{Style.RESET_ALL}\n")

    try:
        from src.ml.predictor import AdPredictor
        predictor = AdPredictor()
    except Exception as exc:
        print(_err(f"Could not load predictor: {exc}"))
        return 1

    if not predictor.is_ready():
        print(_warn("Model not trained yet. Run:  python -m src.cli.cli train"))
        return 1

    try:
        result = predictor.predict(
            ad_copy=ad_copy,
            industry=industry,
            has_cod=has_cod,
            mentions_price=mentions_price,
        )
    except Exception as exc:
        print(_err(f"Prediction failed: {exc}"))
        return 1

    score = result["score"]
    label = result["label"]
    feedback = result.get("feedback", [])

    # Score colour
    if score >= 70:
        score_colour = Fore.GREEN
    elif score >= 40:
        score_colour = Fore.YELLOW
    else:
        score_colour = Fore.RED

    _banner("Ad Grade Result")
    print(f"  {'Score':<28}{score_colour}{Style.BRIGHT}{score}/100{Style.RESET_ALL}")
    print(f"  {'Label':<28}{score_colour}{Style.BRIGHT}{label}{Style.RESET_ALL}")
    print(f"\n  {Fore.CYAN}Top features / feedback:{Style.RESET_ALL}")
    for line in feedback:
        print(f"    {Fore.WHITE}*{Style.RESET_ALL} {line}")

    return 0


# ---------------------------------------------------------------------------
# Command: status
# ---------------------------------------------------------------------------

def cmd_status(_args: argparse.Namespace) -> int:
    _banner("AdLens PK - System Status")

    # 1. Total ads in DB + breakdown by industry
    try:
        from src.db.repository import get_all_ads, init_db
        init_db()
        all_ads = get_all_ads()
        total = len(all_ads)
        print(_kv("Total ads in DB", str(total)))

        industry_counts: dict = {}
        for a in all_ads:
            ind = a.get("industry", "unknown")
            industry_counts[ind] = industry_counts.get(ind, 0) + 1

        print(f"\n  {Fore.CYAN}Ads by industry:{Style.RESET_ALL}")
        for ind, count in sorted(industry_counts.items(), key=lambda x: -x[1]):
            print(f"    {Fore.WHITE}{ind:<30}{Style.RESET_ALL} {count}")
    except Exception as exc:
        print(_warn(f"DB unavailable: {exc}"))

    # 2. Model status
    print()
    try:
        from src.ml.scheduler_hook import get_model_status
        ms = get_model_status()
        if ms.get("model_exists"):
            trained_at = ms.get("last_trained")
            trained_str = trained_at.strftime("%Y-%m-%d %H:%M") if isinstance(trained_at, datetime) else str(trained_at)
            print(_kv("Model status", _ok("Trained")))
            print(_kv("Last trained", trained_str))
            print(_kv("Training records", str(ms.get("training_records", "?"))))
            acc = ms.get("model_accuracy", 0)
            print(_kv("Model accuracy", f"{acc*100:.1f}%"))
        else:
            print(_kv("Model status", _warn("Not trained - run: python -m src.cli.cli train")))
    except Exception as exc:
        print(_warn(f"Model status unavailable: {exc}"))

    # 3. Scheduler next run
    print()
    try:
        from src.core import scheduler as sched_mod
        sched = sched_mod._scheduler
        if sched and sched.running:
            jobs = sched.get_jobs()
            if jobs:
                next_run = jobs[0].next_run_time
                next_str = next_run.strftime("%Y-%m-%d %H:%M") if next_run else "unknown"
                print(_kv("Scheduler", _ok("Active (6h interval)")))
                print(_kv("Next scheduled run", next_str))
            else:
                print(_kv("Scheduler", _ok("Active - no jobs registered")))
        else:
            print(_kv("Scheduler", _warn("Not running (start the desktop app to activate)")))
    except Exception as exc:
        print(_kv("Scheduler", _warn(f"Status check failed: {exc}")))

    # 4. Kaggle datasets
    print()
    try:
        import os
        kaggle_dir = os.path.join("src", "data", "kaggle")
        if os.path.isdir(kaggle_dir):
            csvs = [f for f in os.listdir(kaggle_dir) if f.lower().endswith(".csv")]
            print(_kv("Kaggle datasets", str(len(csvs))))
            for csv_name in csvs:
                print(f"    {Fore.WHITE}*{Style.RESET_ALL} {csv_name[:60]}")
        else:
            print(_kv("Kaggle datasets", _warn("src/data/kaggle/ not found")))
    except Exception as exc:
        print(_warn(f"Kaggle check failed: {exc}"))

    print()
    return 0


# ---------------------------------------------------------------------------
# Command: watchlist
# ---------------------------------------------------------------------------

def cmd_watchlist(args: argparse.Namespace) -> int:
    if args.add:
        brand = args.add.strip()
        industry = (args.industry or "General").strip()
        print(_h(f"\nAdding '{brand}' to watchlist (industry: {industry})..."))
        try:
            from src.db.watchlist import add_to_watchlist
            entry = add_to_watchlist(page_name=brand, industry=industry)
            print(_ok(f"Added: {entry.get('page_name', brand)}"))
        except Exception as exc:
            print(_err(f"Failed to add: {exc}"))
            return 1

    if args.list or not args.add:
        print(_h("\nCompetitor Watchlist"))
        try:
            from src.db.watchlist import get_watchlist
            entries = get_watchlist(active_only=True)
        except Exception as exc:
            print(_err(f"Failed to load watchlist: {exc}"))
            return 1

        if not entries:
            print(_warn("  Watchlist is empty. Add a brand with:"))
            print(_warn('  python -m src.cli.cli watchlist --add "Brand Name" --industry fashion'))
            return 0

        _banner(f"Active entries: {len(entries)}")
        header = (
            f"  {'Page Name':<30} {'Industry':<18} {'Added':<16} "
            f"{'Last Seen':<16} {'Total Ads'}"
        )
        print(f"{Fore.CYAN}{header}{Style.RESET_ALL}")
        print(_rule("·"))
        for e in entries:
            print(
                f"  {Fore.WHITE}{str(e.get('page_name','')):<30}{Style.RESET_ALL}"
                f" {str(e.get('industry','')):<18}"
                f" {str(e.get('added_at',''))[:16]:<16}"
                f" {str(e.get('last_seen_at','Never'))[:16]:<16}"
                f" {e.get('total_ads_found', 0)}"
            )

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli.cli",
        description="AdLens PK - Pakistani Digital Ad Intelligence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.cli status
  python -m src.cli.cli fetch --industry fashion
  python -m src.cli.cli fetch --industry fashion --live
  python -m src.cli.cli analyze --industry fashion
  python -m src.cli.cli train
  python -m src.cli.cli grade --copy "Sale 50% off! Rs. 1499 COD available." --industry fashion
  python -m src.cli.cli watchlist --add "Khaadi" --industry fashion
  python -m src.cli.cli watchlist --list
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch ads and save to DB")
    p_fetch.add_argument("--industry", default="general", help="Industry/niche (default: general)")
    p_fetch.add_argument("--live", action="store_true", help="Use live Playwright scraper instead of demo dataset")
    p_fetch.add_argument("--max-ads", type=int, default=100, dest="max_ads", help="Max ads for live scrape (default: 100)")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze ads for an industry from the DB")
    p_analyze.add_argument("--industry", required=True, help="Industry to analyze")

    # train
    sub.add_parser("train", help="Train the ad survival ML model")

    # grade
    p_grade = sub.add_parser("grade", help="Grade a single ad copy")
    p_grade.add_argument("--copy", required=True, help="Ad copy text to grade")
    p_grade.add_argument("--industry", default="general", help="Industry context (default: general)")

    # status
    sub.add_parser("status", help="Show system status: DB, model, scheduler, Kaggle")

    # watchlist
    p_watch = sub.add_parser("watchlist", help="Manage competitor watchlist")
    p_watch.add_argument("--add", metavar="BRAND", help="Brand page name to add")
    p_watch.add_argument("--industry", default="General", help="Industry for the brand (default: General)")
    p_watch.add_argument("--list", action="store_true", help="List all active watchlist entries")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "fetch":     cmd_fetch,
        "analyze":   cmd_analyze,
        "train":     cmd_train,
        "grade":     cmd_grade,
        "status":    cmd_status,
        "watchlist": cmd_watchlist,
    }

    try:
        return dispatch[args.command](args)
    except KeyboardInterrupt:
        print(_warn("\nInterrupted."))
        return 130
    except Exception as exc:
        print(_err(f"\nUnexpected error: {exc}"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
