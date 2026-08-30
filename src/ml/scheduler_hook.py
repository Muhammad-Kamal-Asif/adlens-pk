"""
APScheduler integration and model status helpers for AdLens PK ML pipeline.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_STATUS_PATH = os.path.join(os.path.dirname(__file__), "models", "status.json")


# ── Status file helpers ───────────────────────────────────────────────────────

def get_model_status() -> dict:
    """
    Return current model status from src/ml/models/status.json.
    Keys: model_exists (bool), last_trained (datetime | None),
          training_records (int), model_accuracy (float | None).
    """
    if not os.path.exists(_STATUS_PATH):
        return {
            "model_exists": False,
            "last_trained": None,
            "training_records": 0,
            "model_accuracy": None,
        }

    try:
        with open(_STATUS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        last_trained_raw = data.get("last_trained")
        last_trained: Optional[datetime] = None
        if last_trained_raw:
            try:
                last_trained = datetime.fromisoformat(last_trained_raw)
            except (ValueError, TypeError):
                pass

        return {
            "model_exists": bool(data.get("model_exists", False)),
            "last_trained": last_trained,
            "training_records": int(data.get("training_records", 0)),
            "model_accuracy": data.get("accuracy"),
        }
    except Exception as exc:
        logger.error(f"Failed to read model status: {exc}")
        return {
            "model_exists": False,
            "last_trained": None,
            "training_records": 0,
            "model_accuracy": None,
        }


def save_model_status(records_used: int, accuracy: float, model_path: str) -> None:
    """Persist training results to src/ml/models/status.json."""
    os.makedirs(os.path.dirname(_STATUS_PATH), exist_ok=True)
    payload = {
        "model_exists": True,
        "last_trained": datetime.utcnow().isoformat(),
        "training_records": records_used,
        "accuracy": accuracy,
        "model_path": model_path,
    }
    try:
        with open(_STATUS_PATH, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except Exception as exc:
        logger.error(f"Failed to save model status: {exc}")


# ── Retrain helpers ───────────────────────────────────────────────────────────

def trigger_manual_retrain() -> dict:
    """
    Run a training cycle synchronously.
    Returns dict: success, records_used, accuracy, model_path,
                  duration_seconds, error (only on failure).
    """
    from src.ml.trainer import run

    start = time.monotonic()
    try:
        result = run()
        duration = time.monotonic() - start

        records_used = int(result.get("records_used", 0))
        accuracy = float(result.get("accuracy", 0.0))
        model_path = str(result.get("model_path", ""))

        save_model_status(records_used, accuracy, model_path)

        logger.info(
            f"Manual retrain complete: {records_used} records, "
            f"accuracy={accuracy:.4f}, duration={duration:.1f}s"
        )
        return {
            "success": True,
            "records_used": records_used,
            "accuracy": accuracy,
            "model_path": model_path,
            "duration_seconds": round(duration, 2),
        }
    except Exception as exc:
        duration = time.monotonic() - start
        logger.error(f"Manual retrain failed: {exc}")
        return {
            "success": False,
            "records_used": 0,
            "accuracy": 0.0,
            "model_path": "",
            "duration_seconds": round(duration, 2),
            "error": str(exc),
        }


def schedule_weekly_retrain(scheduler) -> None:
    """
    Register a weekly retrain job on the given APScheduler instance.
    Job id: 'adlens_weekly_retrain'. Safe to call multiple times —
    replaces any existing job with the same id.
    """
    from src.ml.trainer import run

    def _retrain_job() -> None:
        logger.info("Scheduled weekly retrain starting.")
        try:
            result = run()
            save_model_status(
                result["records_used"],
                result["accuracy"],
                result["model_path"],
            )
            logger.info(
                f"Weekly retrain complete: {result['records_used']} records, "
                f"accuracy={result['accuracy']:.4f}"
            )
        except Exception as exc:
            logger.error(f"Weekly retrain job failed: {exc}")

    job_id = "adlens_weekly_retrain"

    # Replace if already scheduled
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        _retrain_job,
        trigger="interval",
        weeks=1,
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"Scheduled weekly retrain job '{job_id}'.")
