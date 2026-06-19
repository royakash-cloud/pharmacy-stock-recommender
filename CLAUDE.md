# Smart Stock Recommender — Claude Code Build Prompt
# Pharmacy Daily Product Suggestion System — Version 1
# Architecture: Static Site (no live backend server)

---

## Who I Am
I am a retail pharmacist with 10+ years of experience running an
independent pharmacy in South Kolkata. I have basic technical
understanding but have never built a software project end to end.
I want to learn the complete development process with industry
standards. Guide me step by step, explaining every decision.

---

## The Problem
During busy pharmacy shifts I simultaneously dispense medicines,
counsel patients, manage billing and handle cash. Reorder tracking
consistently falls through the gap — not carelessness but a
structural attention problem.

---

## The Solution
A Smart Stock Recommender that shows 50 products to check and
reorder every day, across a 31-day cycle with zero repetition.
For each product it also shows the recommended purchase quantity,
adjusted for seasonal demand patterns.

---

## Architecture Decision — Why Static, Not a Live Server

The data only changes once a month, when I upload the latest
purchase history and regenerate the schedule. There is no need
for a server running 24/7 waiting for that one monthly event.

So the system works like this:
```
Run a Python script on my laptop (once a month)
        ↓
Script reads the purchase CSV, runs the algorithm
        ↓
Saves the result as one JSON file: schedule.json
        ↓
Push schedule.json to GitHub
        ↓
A simple HTML page (hosted free on GitHub Pages) reads
schedule.json directly and shows today's 50 products
        ↓
I open the GitHub Pages URL on my phone — works anywhere,
no server, no login, no cost, never sleeps
```

This is called a **static site** — there is no backend API,
no database server, nothing that needs to "stay running."
The Python script is a one-time/monthly tool I run myself, not
a live service. This avoids all hosting costs and complexity
that come with running a server continuously.

---

## Data Available
- Historical purchase CSV: 3 financial years
  (FY 2023-24, 2024-25, 2025-26)
- Columns: Product Name, BillDate, Qty.
- ~23,135 rows, ~3,673 unique products
- Monthly purchase CSV (for retraining):
  Columns: Product Name, Date, Qty
- Indian financial year: April = month 1, March = month 12

---

## Algorithm — Two Layers

### Layer 1: Base Recommender

#### Step 1 — Recency Score
Exponential weights on monthly purchase quantities:
- weight(n) = exp(-0.1 * n) where n = months ago
- recency_score = weighted sum of monthly quantities
- Only last 36 months used (3 years)

#### Step 2 — Velocity Tiers
Sort all products by recency_score:
- Top 33%    → Fast movers   → 15 slots per day
- Middle 33% → Medium movers → part of 35 slots
- Bottom 33% → Slow movers   → part of 35 slots

#### Step 3 — 31-Day Schedule
- Fast movers: placed on days matching their historical
  peak day-of-month purchase pattern
- Medium + Slow: round-robin rotation
- Hard constraint: zero product repetition in a 31-day cycle


### Layer 2: Seasonal Index (already implemented)

The file `seasonal_index_engine.py` is already written and tested.
Copy it as-is — do not modify it. It contains 6 functions:

| Function | Purpose |
|---|---|
| prepare_data(df) | Normalise dates, add FY fields |
| compute_seasonal_index(df) | Core SI per product per month |
| detect_product_season_category(si_data) | Auto-classify by season |
| generate_seasonal_alerts(si_data, date) | Pre-season alerts |
| apply_seasonal_to_recs(daily_recs, si_data, month) | Modify daily recs |
| run_seasonal_pipeline(df_raw, daily_recs, date) | Master function |

#### How Seasonal Index Works
```
For each product P, for each calendar month M:
  avg_monthly_qty  = total_qty / 36 months (growth-adjusted)
  avg_qty_in_month = mean(qty in month M, across 3 years)
  SI[P][M]         = avg_qty_in_month / avg_monthly_qty

SI = 1.0 → normal month
SI = 1.5 → 50% above average (PEAK) → stock up 2 weeks early
SI = 2.0 → 100% above average (STRONG PEAK)
SI = 0.5 → 50% below average (OFF season)
```

#### How Seasonal Layer Modifies Recommendations
```
Rule 1 — BOOST:
  If SI >= 1.5 AND product is Slow/Medium mover
  → Promote to Fast mover for this month

Rule 2 — SUPPRESS:
  If SI < 0.5 AND product is Fast mover
  → Demote to Slow for this month

Rule 3 — QUANTITY SCALING:
  adjusted_rec_qty = base_rec_qty × SI
  Example: ELECTRAL POWDER base = 20 units
    June (SI=2.2) → recommend 44 units
    January (SI=0.4) → recommend 8 units
```

#### Confidence — Only Use Reliable Signals
```
HIGH confidence   → appears in all 3 years
                  + >= 3 transactions in that month
                  + consistency score >= 0.5

MEDIUM confidence → appears in at least 2 of 3 years
                  + >= 2 transactions

LOW / IGNORE      → insufficient data (ignored)
```

### Recommended Purchase Quantity
```
base_qty         = avg_monthly_qty(last 3 years) / 4
recommended_qty  = base_qty × SI[product][current_month]
minimum          = 1 (never show zero)
```
Dividing by 4 gives approximately one week of stock.
Multiplying by SI scales up for peak season, down for off season.

---

## Features — Version 1 Only
1. Daily view — today's 50 products + recommended qty + SI badge
2. Calendar — navigate all 31 days of the cycle
3. Retrain — re-run the local script with new monthly CSV
4. Export — today's 50 products as CSV (button on the page)

## NOT in Version 1
- Miss log
- Stock register
- Expiry tracker
- Stock quantity input per product
- Any live backend server, database, or API

---

## Tech Stack
- Training script: Python (pandas, numpy) — run locally, not deployed
- Output: a single JSON file (schedule.json)
- Viewer: HTML + CSS + Vanilla JavaScript — reads JSON directly
- Hosting: GitHub Pages (free, static, never sleeps, no card needed)
- Existing: seasonal_index_engine.py (already written — import it)
- Version control: Git + GitHub

No FastAPI. No SQLite. No Render/Railway. No Bruno.
The entire "backend" is a script you run on your own laptop
whenever you want to retrain.

---

## Folder Structure
```
daily-recommender/
├── scripts/
│   ├── explore.py               ← EDA — run once to understand data
│   ├── clean_products.py        ← product name dedup (auto + flag for review)
│   ├── algorithm.py             ← recency score, velocity, schedule
│   ├── seasonal_index_engine.py ← ALREADY WRITTEN — copy here, do not modify
│   ├── recommender.py           ← combines base + seasonal → final rec qty
│   ├── generate.py              ← MASTER SCRIPT — run this to retrain
│   │                              loads CSV → runs algorithm → writes
│   │                              docs/schedule.json
│   └── requirements.txt
├── docs/
│   ├── index.html               ← the viewer page (this is what's hosted)
│   ├── schedule.json            ← generated output — the only "database"
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js               ← reads schedule.json, renders the UI
├── data/
│   └── raw/                     ← original CSVs (gitignored)
├── logs/                        ← local log files from generate.py runs
├── .gitignore
├── README.md
└── CLAUDE.md                    ← this file
```

Note: GitHub Pages serves whatever is inside the `docs/` folder
directly as a website — this is why the viewer and the JSON
output both live there.

---

## Development Phases

### Phase 1: Project Setup (Day 1)
1. Ask me to create GitHub repo called daily-recommender and share URL
2. Clone repo locally
3. Create folder structure above
4. Python virtual environment: python -m venv venv
5. Activate venv and install:
   pip install pandas numpy openpyxl rapidfuzz
6. Copy seasonal_index_engine.py into scripts/
7. Create requirements.txt: pip freeze > requirements.txt
8. .gitignore — exclude: venv/ data/raw/ __pycache__/ logs/
9. Create a simple logging setup in generate.py:
   - Logs to console (so I see what's happening when I run it)
   - Logs to a local file logs/generate.log for later review
   - Three levels: INFO (normal events), WARNING (handled issues),
     ERROR (something failed)
10. README.md skeleton
11. First commit: "Initial project structure"

Explain: what a virtual environment is and why we need it,
what .gitignore does, why raw data is excluded from git,
why we log even for a script we run ourselves
(so that if something looks wrong weeks later, we can check
 the log file instead of guessing)

---

### Phase 2: Data Pipeline (Day 2-3)

#### Phase 2A — Explore the Data First
Before writing algorithm.py, write `scripts/explore.py` that:
1. Loads the historical CSV from data/raw/
2. Prints date range (earliest and latest BillDate)
3. Prints total rows and unique product count
4. Prints top 20 products by total quantity
5. Prints how many rows fall in the last 3 years vs older
6. Checks for data quality issues:
   - Missing values
   - Duplicate rows
   - Negative or zero quantities
   - Inconsistent date formats
Run it and explain what the output tells us before moving forward.

#### Phase 2B — Product Name Deduplication
Real pharmacy billing data has the same product entered inconsistently
over the years (e.g. "PARACETAMOL 500MG" vs "PARACETAMOL 500 MG" vs
"Paracetamol-500mg"). Left unfixed, this splits purchase history across
fake "different" products and weakens both recency and seasonal scores.

Write `scripts/clean_products.py` with two layers:

Layer 1 — Automated safe cleaning (always applied):
- Strip leading/trailing whitespace
- Convert to uppercase
- Collapse multiple spaces into one
- Remove trailing punctuation (. , -)
- Standardize common abbreviations (TABS/TABLET → TAB, MG. → MG)

Layer 2 — Fuzzy match for manual review (never auto-merge):
- Use the rapidfuzz library to compare all remaining product names
- Flag pairs with similarity score above 85% as "possible duplicates"
- Output a file `possible_duplicates.csv` with columns:
  Product A, Product B, Similarity %, Qty A, Qty B
- I will manually review this file and decide which pairs are truly
  the same product vs genuinely different strengths/forms
  (e.g. "TELPRES 40" and "TELPRES 40 AM" are different drugs —
  do not auto-merge anything, only flag for my review)
- Once I provide a final mapping (old_name → correct_name), apply it
  permanently as a one-time cleaning step before any algorithm runs

Explain: why this matters for data quality, what fuzzy matching means,
why we never auto-merge without human review

#### algorithm.py
- Load and clean data (using clean_products.py logic)
- Filter: keep only rows where BillDate >= today - 3 years
- compute_recency_scores(monthly_df) → recency_score per product
- assign_velocity_tiers(scores) → Fast/Medium/Slow
- generate_schedule(tiers, monthly_df) → 31-day schedule, no duplicates

#### recommender.py
- Uses seasonal_index_engine.run_seasonal_pipeline()
- base_qty per product = avg_monthly_qty / 4
- final_qty = base_qty × SI[product][current_month]
- minimum final_qty = 1

#### generate.py — THE MASTER SCRIPT
This is the only script I run to retrain. It:
1. Loads the CSV from data/raw/
2. Runs cleaning, algorithm, and seasonal pipeline in order
3. Builds the full output structure:
   {
     "generated_on": "2026-06-16",
     "days": {
       "1": {
         "products": [
           {"name": "PARACETAMOL 500MG", "recommended_qty": 44,
            "si": 2.2, "si_category": "PEAK", "velocity": "F"},
           ... 50 products
         ]
       },
       ... all 31 days
     },
     "alerts": [ ...pre-season alerts... ]
   }
4. Writes this to docs/schedule.json
5. Logs a summary: how many products, how many alerts, any warnings

Commit: "Data pipeline working — generate.py produces schedule.json"

Explain: what exponential decay means in plain English,
why we filter to 3 years, what SI=1.5 means in plain English,
why we divide by 4 for recommended quantity,
why everything is bundled into one JSON file instead of
separate files or a database

---

### Phase 3: The Viewer Page (Day 4-6)

#### docs/index.html
- Header: "Day 12 of 31 — Tuesday 16 June 2026"
  (JavaScript calculates which day of the 31-day cycle today is)
- Seasonal banner if any alerts exist:
  "⚠ 3 products entering PEAK season — check alerts"
- Table with columns: # | Product Name | Rec Qty | Season
- Season badge: 🔴 PEAK | 🟡 HIGH | ⚪ NORMAL | 🔵 LOW | ⚫ OFF
- Simple calendar — 31 day buttons, click to view any day
- "Download Today's List as CSV" button
- "View All Alerts" section

#### docs/js/app.js
- On page load: fetch('schedule.json') and parse it
- Calculate today's day number in the 31-day cycle
- Render the table for that day
- Handle calendar day clicks — switch the displayed day
- Handle CSV download — convert today's data to CSV in-browser
  and trigger a download (no server needed for this)

#### docs/css/style.css
- Mobile-first — this will mostly be viewed on a phone
- Clean, readable table
- Color-coded season badges

Commit: "Viewer page complete — reads schedule.json correctly"

Explain: what fetch() does when reading a local JSON file,
what async/await means, why no server is needed for this step,
how a CSV download can be triggered entirely in the browser

---

### Phase 4: Polish (Day 7)
1. What if schedule.json fails to load? Show a clear message
   ("No schedule found — has generate.py been run yet?")
2. What if today's date is outside the current cycle? Handle gracefully
3. Loading message while fetching schedule.json
4. Test on phone browser
5. Add "Last updated: [date]" using the generated_on field

Commit: "Polish and error handling complete"

Explain: why even a simple static page needs basic error handling,
what the user sees if something is missing

---

### Phase 5: Deploy to GitHub Pages (Day 8)
1. Push the docs/ folder (with schedule.json already generated) to GitHub
2. On GitHub: repository Settings → Pages
3. Source: Deploy from branch → main → /docs folder
4. Save — GitHub gives a live URL:
   https://royakash-cloud.github.io/daily-recommender/
5. Open this URL on phone — confirm today's 50 products show correctly
6. Bookmark it / add to phone home screen

Commit: "Live on GitHub Pages"

Explain: what GitHub Pages is, why this works without any
server cost, what happens when the repo is updated
(GitHub Pages auto-redeploys on every push to main)

---

### Phase 6: Monthly Retrain Routine (ongoing, not a "phase")
Each month, the routine is:
1. Export latest purchase data to CSV
2. Place it in data/raw/
3. Run: python scripts/generate.py
4. Check the console output / logs/generate.log for any warnings
5. Confirm docs/schedule.json was updated
6. git add docs/schedule.json
7. git commit -m "Retrain — [month] [year] data"
8. git push
9. GitHub Pages auto-updates within a minute — refresh the phone page

Write this exact routine into the README.md so it's documented
clearly enough that I can do it myself every month without help.

---

## Rules for Claude Code
- Explain every terminal command before running it
- Explain what each new file does when created
- Commit after every working feature with a clear message
- When something breaks: explain WHY before fixing it
- At each phase end: summarise what was built and why it matters
- Add comments in every file explaining what the code does
- If two approaches exist: explain both, then say which and why
- Never skip steps — understanding is the goal, not just speed
- Do not introduce a backend server, database, or API of any kind —
  this project is intentionally a static site with a local script

---

## Interview Questions I Must Be Able to Answer

### About the architecture
1. Why did you choose a static site instead of a live backend server?
2. What would change if this needed real-time updates instead of
   monthly retraining?
3. What is GitHub Pages and how does it differ from a hosting
   platform like Render or Railway?

### About the algorithm
4. What does the recommender do in simple terms?
5. What is a seasonal index and how is it calculated?
6. Why 3 years of data and not more?
7. What does SI=2.2 mean for a product like ELECTRAL POWDER?
8. What is a velocity tier and how are they calculated?
9. Why divide recommended quantity by 4?
10. What is exponential decay and why use it for recency?

### About the data
11. How did you handle inconsistent product names in the raw data?
    Why didn't you fully automate the merging?
12. How would you debug an issue if generate.py produced
    wrong-looking output?

### About the product
13. What real problem does this solve?
14. What would you add in Version 2?
15. At what point would this need to become a real backend
    (with a database and API) instead of a static site?
16. How was Claude used in this build?

---

## Success Criteria
- generate.py runs successfully on my laptop and produces schedule.json
- The viewer page works locally by opening docs/index.html
- Live on GitHub Pages — works on phone via the live URL
- Shows 50 products per day with recommended qty and SI badge
- Seasonal adjustment visible:
  ELECTRAL POWDER shows higher qty in June than December
  DUOLIN shows higher qty in November than July
- Calendar works across all 31 days
- No product appears twice in the 31-day cycle
- Monthly retrain routine documented in README and works end to end
- CSV export downloads with correct data, no server involved
- I can explain every part in my own words, including why this
  architecture has no backend server

---

## Start Here
Begin with Phase 1.
First ask me to:
1. Create a new repository on github.com named daily-recommender
2. Share the repository URL

Then:
- Clone the repo
- Create the complete folder structure
- Set up Python virtual environment
- Install all dependencies
- Create .gitignore and README.md skeleton
- Make the first Git commit with message "Initial project structure"

Show every command. Explain each one before running it.
Do not proceed to Phase 2 until I confirm Phase 1 is working.
