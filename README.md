# Pharmacy Stock Recommender

**Live:** https://royakash-cloud.github.io/pharmacy-stock-recommender/

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

See [RETRAIN.md](RETRAIN.md) — run `.\retrain.ps1` after dropping the
new export into `data/raw/`.

## Status

Phases 1-5 complete: project setup, data pipeline, algorithm/recommender,
viewer, polish, and live deploy on GitHub Pages. Phase 6 (monthly
retrain routine, above) is the ongoing operational step.
