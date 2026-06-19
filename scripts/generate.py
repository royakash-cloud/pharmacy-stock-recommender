"""
Master script — run this once a month to retrain the schedule.
Loads the purchase CSV, runs cleaning + algorithm + seasonal pipeline,
and writes docs/schedule.json.

Usage:
    python scripts/generate.py
"""

import logging
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "generate.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),          # prints to console
        logging.FileHandler(LOG_FILE),    # also saves to logs/generate.log
    ],
)

logger = logging.getLogger("generate")


def main():
    logger.info("generate.py started")
    # Phase 2 will add: load CSV -> clean -> algorithm -> seasonal pipeline -> write schedule.json
    logger.info("generate.py finished (pipeline not yet implemented)")


if __name__ == "__main__":
    main()
