# Engineering Log — Pharmacy Stock Recommender

Record of architecture/algorithm decisions and notable debugging
during this project, kept for resume and interview prep. Each entry
covers the problem, the decision/fix, and why — the kind of detail
that doesn't survive in commit messages alone.

---

## 1. Architecture: static site instead of a live backend

**Decision:** No server, no database, no API. A local Python script
(`scripts/generate.py`) is run manually once a month; it writes a
single `docs/schedule.json`; a static HTML/CSS/JS page on GitHub
Pages reads that JSON directly.

**Why:** The underlying data (purchase history) only changes once a
month, when new data is exported and the script is rerun by hand.
A server running 24/7 has nothing to do the other 29 days — it would
add hosting cost and operational surface area for zero benefit.
Tradeoff made explicit: this design would need to change (real
backend + DB + API) if requirements shifted to multi-user access,
real-time updates, or write-back from the UI (e.g. logging actual
stock counts) — none of which are in scope for v1.

## 2. Algorithm: two-layer recommendation engine

**Layer 1 — recency + velocity:**
- `recency_score` per product = exponential-decay-weighted sum of
  monthly quantities, `weight(n) = exp(-0.1 * n)`, n = months before
  an anchor month, over a 36-month (3-year) window. Exponential decay
  was chosen over a flat average so a product bought heavily 2 years
  ago but rarely since doesn't outrank one that's been selling
  steadily this quarter.
- Products are split into **Fast / Medium / Slow** velocity tiers by
  recency score (top/middle/bottom third).
- A 31-day schedule is built with a hard zero-repetition constraint:
  15 Fast-mover slots/day placed on each product's historical
  peak-day-of-month, plus 35 Medium/Slow slots/day round-robined —
  sized so capacity (31 × 15, 31 × 35) exactly matches the number of
  products selected into each tier, guaranteeing every slot fills
  without collisions.

**Layer 2 — seasonal index (`seasonal_index_engine.py`, treated as a
fixed, unmodified dependency):**
- `SI[product][month] = avg_qty_in_month / avg_monthly_qty`, computed
  per product per calendar month from 3 years of history.
- SI drives both a **quantity multiplier** (`recommended_qty = base_qty
  × SI`) and **tier promotion/demotion** (e.g. a Slow mover with
  SI ≥ 1.5 gets boosted to Fast for that month; a Fast mover with
  SI < 0.5 gets demoted).
- Confidence gating (HIGH/MEDIUM/LOW) prevents products with thin
  history from generating misleading seasonal signals.

**Engineering decision — SI display cap (commit `09aa1a1`):**
Low-volume products with a sharply declining 3-year trend can produce
a near-zero growth-adjusted baseline; dividing by that near-zero
number then produces SI values like 40× from a single ordinary
purchase — noise, not real seasonality. Capped `SI_DISPLAY_CAP = 5.0`
in `recommender.py`, rescaling the recommended quantity proportionally
so the displayed SI and the actual quantity stay consistent with each
other, instead of silently lying about the multiplier.

## 3. Data quality: human-in-the-loop product name cleanup

**Problem:** ~3,673 unique product strings in the raw billing export,
many of which are the same drug typed inconsistently across 3 years
("PARACETAMOL 500MG" vs "PARACETAMOL 500 MG" vs "Paracetamol-500mg").
Left unfixed, this splits one product's purchase history across
multiple fake "different" products and weakens both the recency score
and the seasonal index.

**Decision — two layers, deliberately asymmetric in trust:**
- Layer 1 (always applied, automatic): whitespace/case/punctuation
  normalization and abbreviation standardization (TABS/TABLET → TAB).
  Safe because it can never change which drug a name refers to.
- Layer 2 (fuzzy match via `rapidfuzz`, **never auto-merged**): pairs
  scoring ≥ 85% similarity are written to `possible_duplicates.csv`
  for manual review only. Reason: similar-looking names can be
  genuinely different products (e.g. "TELPRES 40" vs "TELPRES 40 AM"
  are different drugs) — an automatic merge here would silently
  corrupt purchase history with no way to detect it later. Confirmed
  merges are applied via an explicit `old_name → correct_name` mapping
  file, so every merge is a traceable, reviewed decision.

## 4. Debugging session: monthly retrain silently ignored new data

**Symptom:** After adding an April–June 2026 purchase export and
rerunning `generate.py`, the output's `anchor_month` (the most recent
month the recommender is aware of) still read 2026-03 — three months
stale — despite the run completing "successfully" with no errors or
warnings.

**Investigation approach** (root-cause first, no fix attempted until
confirmed): checked which files actually exist in `data/raw/` vs.
which files the loader's glob pattern matches; loaded and printed the
date range of each source file individually and combined; traced
`anchor_month` to its exact definition (`monthly["year_month"].max()`
in `algorithm.py`); inspected the new file's raw bytes to rule out a
mislabeled/corrupted export before assuming a date-parsing bug.

**Root causes found (two, compounding):**
1. `clean_products.py`'s loader globbed only `*.xlsx`. The new export
   was named `apr_may_26_27.xls` — a different extension — so it was
   never even opened. No error was raised because, from the glob's
   perspective, the file simply didn't exist.
2. Even with the extension fixed, the file is a genuine legacy Excel
   binary (confirmed via its OLE2 magic bytes, `D0 CF 11 E0 A1 B1 1A
   E1` — ruled out a mislabeled CSV/HTML export, which is a common
   failure mode for POS "export to Excel" features). Reading legacy
   `.xls` requires the `xlrd` package, which wasn't a project
   dependency (`requirements.txt` only had `openpyxl`, which handles
   `.xlsx` only).

**Why this class of bug matters:** it failed silently — `generate.py`
logged "finished successfully," produced a schedule, and gave no
indication that 3 months of real purchase data were missing. A glob
pattern is an implicit, unenforced assumption about file naming that
nothing else in the system checks.

**Fix:**
- `clean_products.py`: glob both `*.xlsx` and `*.xls`.
- Added `xlrd==2.0.2` to `requirements.txt` and installed it.
- Verified end-to-end: combined dataset grew from 71,197 → 74,541
  rows, date range extended to 2026-05-31, `anchor_month` corrected
  to 2026-05, and a full retrain ran cleanly (1,550 scheduled
  products, 1,422 seasonal alerts, up from 969 before the fix —
  consistent with 3 additional months of seasonal signal, not noise).

**Possible follow-up (not yet implemented):** the loader could log a
warning listing any files in `data/raw/` that don't match a supported
extension, so a future mismatched export is caught immediately
instead of silently producing a stale schedule again.

## 5. Operational design: logging for a script with no live monitoring

`generate.py` logs to both console and `logs/generate.log` (INFO/
WARNING/ERROR), and tees the pipeline's own print statements into the
same log file. Decision driven by the fact that this script runs
unattended, once a month, by a non-engineer end user — if a retrain
"looks wrong" weeks later, the log file needs to be enough to
diagnose it without re-running and guessing. This log was exactly
what made the bug in §4 traceable after the fact.
