"""
Combines algorithm.py's 31-day schedule with the seasonal index layer
(seasonal_index_engine.py) to produce each scheduled product's final
recommended purchase quantity and seasonal badge.

recommended_qty = (avg_monthly_qty_last_3yrs / 4) * SI[product][month]
minimum recommended_qty = 1

Usage:
    python scripts/recommender.py
"""

import sys

import pandas as pd

# seasonal_index_engine.py prints unicode arrows ("→"); Windows'
# default console encoding (cp1252) can't display them. We never
# modify that file, so fix the encoding here at the call site instead.
sys.stdout.reconfigure(encoding="utf-8")

from clean_products import load_and_clean_data
from algorithm import (
    MONTHS_LOOKBACK,
    filter_last_3_years,
    compute_monthly_quantities,
    compute_recency_scores,
    assign_velocity_tiers,
    compute_peak_days,
    build_schedule,
    validate_schedule,
)
from seasonal_index_engine import run_seasonal_pipeline

VELOCITY_CODE = {"Fast": "F", "Medium": "M", "Slow": "S"}
VELOCITY_NAME = {v: k for k, v in VELOCITY_CODE.items()}


def prepare_seasonal_input(df):
    """seasonal_index_engine.py expects Product Name / BillDate / Qty.
    We feed it our already Layer-1-cleaned `clean_name` (renamed to
    Product Name) so its seasonal-index keys line up exactly with the
    names used in the schedule -- otherwise SI lookups would silently
    miss every product. Uses the FULL 3-financial-year history (not
    the "today minus 3 years" window used for recency scoring), since
    the engine's own 36-month math expects a clean, complete window."""
    return df[["clean_name", "Date", "Qty."]].rename(
        columns={"clean_name": "Product Name", "Date": "BillDate"}
    )


def compute_base_quantities(df):
    """base_qty = avg monthly quantity over the full 3-year history,
    divided by 4 (~one week of stock). Computed directly so every
    scheduled product gets a base quantity, even ones without enough
    history for a confident seasonal index (those just keep this
    number unscaled, SI treated as neutral 1.0)."""
    total_qty = df.groupby("clean_name")["Qty."].sum()
    return (total_qty / MONTHS_LOOKBACK) / 4


def schedule_to_daily_recs(schedule, base_qty):
    """Converts algorithm.py's schedule dict into the
    {day_str: [[name, rec_qty, mrp, share, vel], ...]} shape
    apply_seasonal_to_recs() expects. mrp/share (price/market-share)
    aren't tracked in this project, so they're passed through as
    None -- the engine only reads them, it doesn't require them."""
    daily_recs = {}
    for day, products in schedule.items():
        daily_recs[str(day)] = [
            [p["name"], float(base_qty.get(p["name"], 0)), None, None, VELOCITY_CODE[p["velocity"]]]
            for p in products
        ]
    return daily_recs


def finalize_recommendations(modified_recs):
    """Rounds final quantities to whole units (never below 1) and
    reshapes each entry into a plain dict for the schedule output."""
    finalized = {}
    for day_str, products in modified_recs.items():
        day_list = []
        for name, qty, _mrp, _share, vel, si_val, si_cat in products:
            final_qty = max(1, round(qty))
            day_list.append({
                "name": name,
                "recommended_qty": int(final_qty),
                "si": round(float(si_val), 2),
                "si_category": si_cat,
                "velocity": VELOCITY_NAME[vel],
            })
        finalized[int(day_str)] = day_list
    return finalized


def build_recommendations(current_date=None):
    current_date = current_date or pd.Timestamp.now()

    df = load_and_clean_data()

    # Recency + schedule layer: "today minus 3 years" so it stays
    # current every time this is rerun on a later date.
    recency_df = filter_last_3_years(df, current_date)
    monthly = compute_monthly_quantities(recency_df)
    scores, anchor_month = compute_recency_scores(monthly)
    tiers = assign_velocity_tiers(scores)
    fast_names = tiers[tiers == "Fast"].index
    peak_days = compute_peak_days(recency_df, fast_names)
    schedule = build_schedule(scores, tiers, peak_days)
    validate_schedule(schedule)

    # Base quantity: full 3-financial-year history (see module docstring).
    base_qty = compute_base_quantities(df)

    # Seasonal layer: also the full 3-financial-year history.
    seasonal_df = prepare_seasonal_input(df)
    daily_recs = schedule_to_daily_recs(schedule, base_qty)
    seasonal_results = run_seasonal_pipeline(seasonal_df, daily_recs=daily_recs, current_date=current_date)

    recommendations = finalize_recommendations(seasonal_results["modified_recs"])

    return {
        "recommendations": recommendations,
        "alerts": seasonal_results["alerts"],
        "seasonal_summary": seasonal_results["seasonal_summary"],
        "anchor_month": str(anchor_month),
    }


def main():
    result = build_recommendations()

    print(f"\nAnchor month: {result['anchor_month']}")
    print(f"Total alerts: {len(result['alerts'])}")
    print(f"Seasonal summary: {result['seasonal_summary']}")

    print("\nSample - Day 1:")
    for p in result["recommendations"][1][:8]:
        print(f"  {p['name']:35s} qty={p['recommended_qty']:>4} si={p['si']:>5} [{p['si_category']:>6}] {p['velocity']}")


if __name__ == "__main__":
    main()
