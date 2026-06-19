
# ══════════════════════════════════════════════════════════════════════════════
# SEASONAL INDEX ENGINE — Production Implementation
# For Indian Pharmacy Purchase Data (3 Financial Years)
# Input:  DataFrame with columns: Product Name, BillDate, Qty.
# Output: seasonal_index dict, alerts, adjusted recommendations
# ══════════════════════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from datetime import datetime, date
from collections import defaultdict

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
MONTH_NAMES = ['','Jan','Feb','Mar','Apr','May','Jun',
               'Jul','Aug','Sep','Oct','Nov','Dec']

# SI thresholds
SI_PEAK    = 1.5   # stock up 2 weeks early
SI_HIGH    = 1.2   # stock up 1 week early
SI_NORMAL_HIGH = 1.0
SI_LOW     = 0.8
SI_OFF     = 0.5   # minimal stock needed

# Minimum data requirements for confidence
MIN_TRANSACTIONS_PER_MONTH = 3
MIN_YEARS_COVERAGE         = 2   # product must appear in at least 2 of 3 years


# ─── STEP 1: LOAD AND PREPARE DATA ───────────────────────────────────────────
def prepare_data(df):
    """
    Normalise raw purchase data to financial year structure.
    Indian FY: April = month 1, March = month 12
    """
    df = df.copy()
    df.columns = df.columns.str.strip()
    df["Product Name"] = df["Product Name"].str.strip().str.upper()
    df["BillDate"]     = pd.to_datetime(df["BillDate"])
    df["Qty."]         = pd.to_numeric(df["Qty."], errors="coerce").fillna(0)

    # Calendar fields
    df["cal_month"] = df["BillDate"].dt.month
    df["cal_year"]  = df["BillDate"].dt.year

    # Financial year fields
    df["fy_month"] = ((df["cal_month"] - 4) % 12) + 1   # Apr=1 … Mar=12
    df["fy_year"]  = df["cal_year"].where(df["cal_month"] >= 4,
                                           df["cal_year"] - 1)
    df["fy_label"] = df["fy_year"].astype(str) + "-" + (
                     df["fy_year"] + 1).astype(str).str[-2:]

    return df


# ─── STEP 2: COMPUTE SEASONAL INDEX ──────────────────────────────────────────
def compute_seasonal_index(df):
    """
    Returns a dict:
      seasonal_index[product][calendar_month] = {
          "si":          float,   # seasonal index value
          "confidence":  str,     # HIGH / MEDIUM / LOW / IGNORE
          "avg_qty":     float,   # avg qty in this month across years
          "baseline":    float,   # avg monthly qty overall
          "growth_rate": float,   # CAGR across the 3 years
          "category":    str,     # PEAK/HIGH/NORMAL/LOW/OFF
      }
    """
    results = {}
    fy_years = sorted(df["fy_year"].unique())   # e.g. [2023, 2024, 2025]
    n_years  = len(fy_years)

    # Group: product × calendar_month × fy_year → total qty
    grp = (df.groupby(["Product Name", "cal_month", "fy_year"])
             .agg(total_qty=("Qty.", "sum"),
                  transactions=("Qty.", "count"))
             .reset_index())

    for prod, prod_df in grp.groupby("Product Name"):
        # ── Year coverage check ──────────────────────────────────────────────
        years_present = prod_df["fy_year"].nunique()
        if years_present < MIN_YEARS_COVERAGE:
            continue   # not enough history

        # ── Overall baseline: avg monthly qty across all 36 months ──────────
        total_qty      = prod_df["total_qty"].sum()
        total_months   = n_years * 12
        avg_monthly    = total_qty / total_months

        if avg_monthly < 0.1:   # essentially zero demand
            continue

        # ── Year-over-year growth rate (CAGR) ───────────────────────────────
        yr_totals = prod_df.groupby("fy_year")["total_qty"].sum()
        if len(yr_totals) >= 2:
            first_yr = yr_totals.iloc[0]
            last_yr  = yr_totals.iloc[-1]
            n_steps  = len(yr_totals) - 1
            if first_yr > 0:
                growth_rate = (last_yr / first_yr) ** (1 / n_steps) - 1
            else:
                growth_rate = 0.0
        else:
            growth_rate = 0.0

        # Growth-adjusted baseline
        adj_baseline = avg_monthly * (1 + growth_rate)

        # ── Per-month seasonal index ─────────────────────────────────────────
        prod_result = {}
        for month in range(1, 13):
            month_df = prod_df[prod_df["cal_month"] == month]

            if month_df.empty:
                # Product never purchased in this month
                prod_result[month] = {
                    "si": 0.0, "confidence": "LOW",
                    "avg_qty": 0.0, "baseline": adj_baseline,
                    "growth_rate": round(growth_rate * 100, 1),
                    "category": "OFF"
                }
                continue

            # Avg qty in this month across all years it appeared
            qty_by_year = month_df.groupby("fy_year")["total_qty"].sum()
            # Fill missing years with 0
            all_year_qty = [qty_by_year.get(y, 0) for y in fy_years]
            avg_month_qty = np.mean(all_year_qty)

            # Seasonal index
            si = avg_month_qty / adj_baseline if adj_baseline > 0 else 0

            # Confidence scoring
            total_txns = month_df["transactions"].sum()
            years_with_data = (qty_by_year > 0).sum()

            consistency = 1.0
            if len(all_year_qty) > 1 and np.mean(all_year_qty) > 0:
                cv = np.std(all_year_qty) / np.mean(all_year_qty)
                consistency = max(0, 1 - cv)   # 0=inconsistent, 1=perfect

            if (years_with_data >= n_years and
                    total_txns >= MIN_TRANSACTIONS_PER_MONTH and
                    consistency >= 0.5):
                confidence = "HIGH"
            elif (years_with_data >= MIN_YEARS_COVERAGE and
                  total_txns >= 2):
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Classify SI category
            if   si >= SI_PEAK:   category = "PEAK"
            elif si >= SI_HIGH:   category = "HIGH"
            elif si >= SI_LOW:    category = "NORMAL"
            elif si >= SI_OFF:    category = "LOW"
            else:                  category = "OFF"

            prod_result[month] = {
                "si":          round(si, 3),
                "confidence":  confidence,
                "avg_qty":     round(avg_month_qty, 1),
                "baseline":    round(adj_baseline, 1),
                "growth_rate": round(growth_rate * 100, 1),
                "category":    category,
            }

        results[prod] = prod_result

    return results


# ─── STEP 3: DETECT SEASONAL CATEGORY PER PRODUCT ───────────────────────────
def detect_product_season_category(si_data):
    """
    Auto-classify each product into a seasonal category
    based on its SI profile across 12 months.
    Returns dict: product → category label
    """
    # Season month groups (calendar months)
    SEASONS = {
        "SUMMER"       : [4, 5, 6],
        "MONSOON"      : [6, 7, 8, 9],
        "SEASON_CHANGE": [2, 3, 10, 11],
        "WINTER"       : [11, 12, 1, 2],
        "FESTIVE"      : [10, 11, 12],
        "CHRONIC"      : list(range(1, 13)),   # checked last
    }

    categories = {}
    for prod, month_data in si_data.items():
        best_category = "CHRONIC"
        best_avg_si   = 0.0

        for season_name, months in SEASONS.items():
            if season_name == "CHRONIC":
                continue
            # Average SI in peak months for this season
            season_sis = [
                month_data[m]["si"]
                for m in months
                if m in month_data and month_data[m]["confidence"] in ("HIGH","MEDIUM")
            ]
            if not season_sis:
                continue
            avg_si = np.mean(season_sis)

            # Non-peak months should be below average
            non_peak = [m for m in range(1,13) if m not in months]
            non_peak_sis = [month_data[m]["si"] for m in non_peak if m in month_data]
            avg_non_peak = np.mean(non_peak_sis) if non_peak_sis else 1.0

            # Strong seasonal = peak much higher than non-peak
            if avg_si > SI_HIGH and avg_si > (avg_non_peak * 1.3):
                if avg_si > best_avg_si:
                    best_avg_si   = avg_si
                    best_category = season_name

        categories[prod] = best_category
    return categories


# ─── STEP 4: GENERATE ALERTS ─────────────────────────────────────────────────
def generate_seasonal_alerts(si_data, current_date=None):
    """
    Generate pre-season stock alerts.
    Fires 2 weeks before a product's peak month starts.

    Returns list of alert dicts sorted by urgency.
    """
    if current_date is None:
        current_date = date.today()

    alerts = []
    cur_month  = current_date.month
    cur_day    = current_date.day
    next_month = (cur_month % 12) + 1

    for prod, month_data in si_data.items():
        for target_month in [cur_month, next_month]:
            if target_month not in month_data:
                continue

            info = month_data[target_month]
            if info["confidence"] not in ("HIGH", "MEDIUM"):
                continue
            if info["si"] < SI_HIGH:
                continue

            # Days until target month starts
            if target_month > cur_month:
                days_away = (32 - cur_day)   # rough days left this month
            elif target_month == cur_month:
                days_away = 0
            else:
                continue

            # Alert window: 14 days for PEAK, 7 days for HIGH
            alert_window = 14 if info["si"] >= SI_PEAK else 7

            if days_away <= alert_window:
                alerts.append({
                    "product":     prod,
                    "month":       target_month,
                    "month_name":  MONTH_NAMES[target_month],
                    "si":          info["si"],
                    "category":    info["category"],
                    "confidence":  info["confidence"],
                    "days_away":   days_away,
                    "avg_qty":     info["avg_qty"],
                    "baseline":    info["baseline"],
                    "suggested_multiplier": round(info["si"], 1),
                    "urgency":     "HIGH" if info["si"] >= SI_PEAK else "MEDIUM",
                })

    # Sort: most urgent first (highest SI, soonest)
    alerts.sort(key=lambda x: (-x["si"], x["days_away"]))
    return alerts


# ─── STEP 5: APPLY TO DAILY RECOMMENDATIONS ──────────────────────────────────
def apply_seasonal_to_recs(daily_recs, si_data, current_month):
    """
    Modify existing daily recommendations with seasonal layer.

    daily_recs: {day_str: [[name, rec_qty, mrp, share, vel], ...]}
    si_data:    seasonal_index output
    current_month: int (1-12)

    Returns:
      modified_recs: same structure with adjusted quantities
      seasonal_summary: {month: {peak_products, off_products, boost_count}}
    """
    modified = {}
    peak_products = []
    off_products  = []
    boost_count   = 0

    for day_str, products in daily_recs.items():
        new_day = []
        for p in products:
            name, rec_qty, mrp, share, vel = p

            prod_si = si_data.get(name.upper(), {}).get(current_month)

            if prod_si and prod_si["confidence"] in ("HIGH", "MEDIUM"):
                si_val   = prod_si["si"]
                si_cat   = prod_si["category"]

                # Adjust recommended quantity
                adj_qty  = round(rec_qty * si_val, 1) if rec_qty > 0 else rec_qty

                # Boost velocity classification
                if si_val >= SI_PEAK and vel in ("S", "M"):
                    vel = "F"   # promote to fast mover this month
                    boost_count += 1
                elif si_val < SI_OFF and vel == "F":
                    vel = "S"   # demote off-season fast mover

                if si_val >= SI_HIGH:
                    peak_products.append(name)
                elif si_val < SI_OFF:
                    off_products.append(name)

                new_day.append([name, adj_qty, mrp, share, vel, si_val, si_cat])
            else:
                # No seasonal data — keep original, add neutral SI
                new_day.append([name, rec_qty, mrp, share, vel, 1.0, "NORMAL"])

        modified[day_str] = new_day

    seasonal_summary = {
        "month":         current_month,
        "month_name":    MONTH_NAMES[current_month],
        "peak_products": list(set(peak_products)),
        "off_products":  list(set(off_products)),
        "boost_count":   boost_count,
        "peak_count":    len(set(peak_products)),
        "off_count":     len(set(off_products)),
    }

    return modified, seasonal_summary


# ─── STEP 6: FULL PIPELINE ───────────────────────────────────────────────────
def run_seasonal_pipeline(df_raw, daily_recs=None, current_date=None):
    """
    Master function — runs the complete seasonal pipeline.

    Usage:
        df = pd.read_excel("total_purchase.xlsx")
        results = run_seasonal_pipeline(df, daily_recs=existing_recs)

    Returns dict with all outputs.
    """
    if current_date is None:
        current_date = date.today()

    print("Step 1: Preparing data...")
    df = prepare_data(df_raw)
    print(f"  → {len(df):,} rows | {df['Product Name'].nunique():,} products | "
          f"{df['fy_year'].nunique()} financial years")

    print("Step 2: Computing seasonal indices...")
    si_data = compute_seasonal_index(df)
    print(f"  → Seasonal index computed for {len(si_data):,} products")

    # Count by confidence
    high = medium = low = 0
    for prod_data in si_data.values():
        for m_data in prod_data.values():
            if m_data["confidence"] == "HIGH":   high   += 1
            elif m_data["confidence"] == "MEDIUM": medium += 1
            else:                                  low    += 1
    print(f"  → HIGH confidence signals: {high:,}")
    print(f"  → MEDIUM confidence signals: {medium:,}")
    print(f"  → LOW confidence signals: {low:,}")

    print("Step 3: Detecting seasonal categories...")
    categories = detect_product_season_category(si_data)
    from collections import Counter
    cat_counts = Counter(categories.values())
    for cat, count in cat_counts.most_common():
        print(f"  → {cat}: {count} products")

    print("Step 4: Generating alerts...")
    alerts = generate_seasonal_alerts(si_data, current_date)
    print(f"  → {len(alerts)} pre-season alerts generated")

    results = {
        "si_data":    si_data,
        "categories": categories,
        "alerts":     alerts,
    }

    if daily_recs is not None:
        print("Step 5: Applying seasonal layer to recommendations...")
        mod_recs, summary = apply_seasonal_to_recs(
            daily_recs, si_data, current_date.month)
        results["modified_recs"] = mod_recs
        results["seasonal_summary"] = summary
        print(f"  → {summary['peak_count']} products boosted for peak season")
        print(f"  → {summary['off_count']} products suppressed (off season)")
        print(f"  → {summary['boost_count']} velocity promotions applied")

    return results


# ─── EXAMPLE USAGE ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Load your data
    df = pd.read_excel("total_purchase.xlsx")

    # Run pipeline
    results = run_seasonal_pipeline(df)

    # Print top seasonal alerts
    print("\nTOP 10 SEASONAL ALERTS:")
    for alert in results["alerts"][:10]:
        print(f"  [{alert['urgency']}] {alert['product']}")
        print(f"    Peak month: {alert['month_name']} | SI: {alert['si']}x")
        print(f"    Avg demand: {alert['avg_qty']} units | "
              f"Suggested order: {alert['suggested_multiplier']}x normal")

    # Print seasonal index for a specific product
    prod = "ELECTRAL POWDER"
    if prod in results["si_data"]:
        print(f"\nSEASONAL INDEX — {prod}:")
        for m in range(1, 13):
            info = results["si_data"][prod][m]
            bar  = "█" * int(info["si"] * 10)
            print(f"  {MONTH_NAMES[m]:>3}: SI={info['si']:>5.2f} "
                  f"[{info['category']:>6}] [{info['confidence']:>6}] {bar}")
