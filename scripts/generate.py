"""
Master script -- run this once a month to retrain the schedule.
Loads the purchase data, runs cleaning + algorithm + seasonal
pipeline (via recommender.py), and writes docs/schedule.json.

Usage:
    python scripts/generate.py
"""

import json
import logging
import os
import sys
import traceback

import pandas as pd

# seasonal_index_engine.py prints unicode arrows ("→"); Windows'
# default console encoding (cp1252) can't display them. Fixed at the
# call site -- we never modify that file.
sys.stdout.reconfigure(encoding="utf-8")

from recommender import build_recommendations

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SCHEDULE_PATH = os.path.join(BASE_DIR, "docs", "schedule.json")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "generate.log")

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  # prints to console
        _file_handler,            # also saves to logs/generate.log
    ],
)
logger = logging.getLogger("generate")


class _Tee:
    """Duplicates writes to multiple streams. Used so every print()
    from the pipeline modules (clean_products / algorithm /
    recommender / seasonal_index_engine) lands in logs/generate.log
    too, not just the one-line summary below -- so a problem spotted
    weeks from now can be diagnosed from the log file alone, instead
    of having to re-run and guess."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def to_jsonable(value):
    """json.dump doesn't know how to serialise numpy/pandas scalar
    types (e.g. numpy.float64 from the seasonal index calculations).
    Converts them to native Python types instead of crashing."""
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def build_schedule_json(result):
    days = {
        str(day): {"products": products}
        for day, products in result["recommendations"].items()
    }
    return {
        "generated_on": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "days": days,
        "alerts": result["alerts"],
    }


def main():
    real_stdout = sys.stdout
    sys.stdout = _Tee(real_stdout, _file_handler.stream)
    try:
        logger.info("generate.py started")

        result = build_recommendations()
        schedule_json = build_schedule_json(result)

        all_names = [p["name"] for d in schedule_json["days"].values() for p in d["products"]]
        total_slots = len(all_names)
        unique_products = len(set(all_names))
        if unique_products != total_slots:
            logger.warning(
                f"Schedule has {total_slots} product slots but only {unique_products} unique "
                "products -- expected zero repetition across the 31-day cycle."
            )

        os.makedirs(os.path.dirname(SCHEDULE_PATH), exist_ok=True)
        with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
            json.dump(schedule_json, f, indent=2, default=to_jsonable)

        logger.info(f"Wrote {SCHEDULE_PATH}")
        logger.info(
            f"Summary: {unique_products} unique products scheduled across 31 days, "
            f"{len(schedule_json['alerts'])} seasonal alerts, anchor month {result['anchor_month']}"
        )
        logger.info("generate.py finished successfully")
    except Exception:
        logger.error("generate.py failed:\n" + traceback.format_exc())
        sys.exit(1)
    finally:
        sys.stdout = real_stdout


if __name__ == "__main__":
    main()
