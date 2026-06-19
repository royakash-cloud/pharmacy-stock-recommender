# Pharmacy Stock Recommender

A Smart Stock Recommender for an independent pharmacy: every day it
surfaces 50 products to check and reorder, rotating across a 31-day
cycle with zero repetition, with quantities adjusted for seasonal
demand. No backend server — it's a static site that reads a JSON
file generated locally once a month.

## Architecture

```
Run scripts/generate.py on your laptop (once a month)
        ↓
Reads the purchase CSV, runs the algorithm
        ↓
Writes docs/schedule.json
        ↓
Push to GitHub
        ↓
docs/index.html (hosted free on GitHub Pages) reads schedule.json
and shows today's 50 products
```

## Folder structure

```
scripts/   Python pipeline (cleaning, algorithm, seasonal index, generate.py)
docs/      The hosted viewer page (index.html, css/, js/) + schedule.json
data/raw/  Your purchase CSVs (not tracked in git — see .gitignore)
logs/      Run logs from generate.py (not tracked in git)
```

## Setup (one-time)

```
python -m venv venv
source venv/Scripts/activate      # Windows Git Bash
pip install -r scripts/requirements.txt
```

## Monthly retrain routine

1. Export the latest purchase data to CSV
2. Place it in `data/raw/`
3. Run: `python scripts/generate.py`
4. Check the console output / `logs/generate.log` for any warnings
5. Confirm `docs/schedule.json` was updated
6. `git add docs/schedule.json`
7. `git commit -m "Retrain — <month> <year> data"`
8. `git push`
9. GitHub Pages auto-updates within a minute — refresh the phone page

## Status

Phase 1 (project setup) complete. Phase 2 (data pipeline) in progress.
