"""
Core recommendation algorithm:
  1. Recency score per product (exponential decay over monthly qty)
  2. Velocity tier per product (Fast / Medium / Slow, by thirds)
  3. 31-day schedule: 15 fast-mover slots + 35 medium/slow slots per
     day, with zero product repetition across the whole cycle.

Usage:
    python scripts/algorithm.py
"""

import numpy as np
import pandas as pd

from clean_products import load_and_clean_data

MONTHS_LOOKBACK = 36           # 3 years
DECAY_RATE = 0.1                # weight(n) = exp(-0.1 * n)
CYCLE_DAYS = 31
FAST_SLOTS_PER_DAY = 15
OTHER_SLOTS_PER_DAY = 35         # medium + slow combined
TOTAL_SLOTS_PER_DAY = FAST_SLOTS_PER_DAY + OTHER_SLOTS_PER_DAY


def filter_last_3_years(df, reference_date=None):
    """Keeps rows within 3 years of reference_date. Defaults to the
    real current date, so the window slides forward automatically
    every time this is rerun on a later date."""
    reference_date = reference_date or pd.Timestamp.now()
    cutoff = reference_date - pd.DateOffset(years=3)
    before = len(df)
    df = df[df["Date"] >= cutoff]
    print(f"Filtered to last 3 years (>= {cutoff.date()}): kept {len(df)} of {before} rows")
    return df


def compute_monthly_quantities(df):
    """Total quantity per product per calendar month."""
    monthly = (
        df.assign(year_month=df["Date"].dt.to_period("M"))
          .groupby(["clean_name", "year_month"])["Qty."]
          .sum()
          .reset_index()
    )
    return monthly


def compute_recency_scores(monthly, anchor_month=None):
    """
    weight(n) = exp(-DECAY_RATE * n), n = months before the anchor
    month. Only the last MONTHS_LOOKBACK months count.

    anchor_month defaults to the most recent month present in the
    data (not today's calendar month) -- the score should reflect
    freshness relative to what's actually been exported, not assume
    purchases from a month you haven't uploaded yet.
    """
    if anchor_month is None:
        anchor_month = monthly["year_month"].max()

    monthly = monthly.copy()
    monthly["ym_num"] = monthly["year_month"].dt.year * 12 + monthly["year_month"].dt.month
    anchor_num = anchor_month.year * 12 + anchor_month.month
    monthly["months_ago"] = anchor_num - monthly["ym_num"]

    monthly = monthly[(monthly["months_ago"] >= 0) & (monthly["months_ago"] < MONTHS_LOOKBACK)]
    monthly["weight"] = np.exp(-DECAY_RATE * monthly["months_ago"])
    monthly["weighted_qty"] = monthly["weight"] * monthly["Qty."]

    scores = monthly.groupby("clean_name")["weighted_qty"].sum().rename("recency_score")
    return scores.sort_values(ascending=False), anchor_month


def assign_velocity_tiers(scores):
    """Splits every product into three equal-sized tiers by recency
    score: Fast (top third), Medium (middle third), Slow (bottom
    third). This label applies to ALL products regardless of whether
    they end up with a schedule slot this cycle -- the seasonal layer
    (seasonal_index_engine.py) also reads this label to decide
    promote/demote rules."""
    ranked = scores.sort_values(ascending=False)
    groups = np.array_split(ranked.index, 3)
    tier_map = {}
    for name in groups[0]:
        tier_map[name] = "Fast"
    for name in groups[1]:
        tier_map[name] = "Medium"
    for name in groups[2]:
        tier_map[name] = "Slow"
    return pd.Series(tier_map, name="velocity")


def compute_peak_days(df, product_names):
    """For each product, the day-of-month (1-31) with the highest
    total historical quantity -- the day fast movers get scheduled
    on, since that's historically when this pharmacy needed to
    reorder them."""
    subset = df[df["clean_name"].isin(product_names)].copy()
    subset["day_of_month"] = subset["Date"].dt.day
    totals = subset.groupby(["clean_name", "day_of_month"])["Qty."].sum()
    peak = totals.groupby(level="clean_name").idxmax().apply(lambda idx: idx[1])
    return peak


def select_top_n(scores, names, n):
    """Highest-recency-score products within `names`, capped at n."""
    pool = scores.loc[scores.index.intersection(names)]
    selected = pool.sort_values(ascending=False).head(n)
    if len(selected) < n:
        print(f"WARNING: only {len(selected)} products available, needed {n}")
    return selected


def place_fast_movers(selected_fast, peak_days):
    """Each fast mover goes on its historical peak day-of-month; if
    that day's 15 slots are full, it moves to the next day in the
    cycle with room. Capacity (31*15) exactly matches the number of
    fast movers selected, so a slot is always found."""
    day_counts = {d: 0 for d in range(1, CYCLE_DAYS + 1)}
    day_assignment = {}
    for name in selected_fast.index:  # already sorted by recency desc
        peak_day = int(peak_days.get(name, 1))
        for offset in range(CYCLE_DAYS):
            day = ((peak_day - 1 + offset) % CYCLE_DAYS) + 1
            if day_counts[day] < FAST_SLOTS_PER_DAY:
                day_assignment[name] = day
                day_counts[day] += 1
                break
    return day_assignment


def interleave(names_a, names_b):
    """Alternates two lists (A, B, A, B, ...) so a round-robin day
    assignment afterwards gives each day an even mix of both, instead
    of e.g. the first 17 days being all A and the rest all B."""
    merged = []
    for a, b in zip(names_a, names_b):
        merged.append(a)
        merged.append(b)
    merged.extend(names_a[len(names_b):])
    merged.extend(names_b[len(names_a):])
    return merged


def place_other_movers(selected_medium, selected_slow):
    """Round-robin across the 31 days, alternating Medium/Slow so
    each day gets a mix of both tiers rather than clustering by tier.
    With exactly 35*31 slots and that many products selected, this
    lands exactly 35/day."""
    ordered_names = interleave(list(selected_medium.index), list(selected_slow.index))
    return {name: (i % CYCLE_DAYS) + 1 for i, name in enumerate(ordered_names)}


def build_schedule(scores, tiers, peak_days):
    fast_needed = FAST_SLOTS_PER_DAY * CYCLE_DAYS
    other_needed = OTHER_SLOTS_PER_DAY * CYCLE_DAYS
    medium_needed = (other_needed + 1) // 2   # 50/50 split, extra slot to Medium
    slow_needed = other_needed // 2

    fast_names = tiers[tiers == "Fast"].index
    medium_names = tiers[tiers == "Medium"].index
    slow_names = tiers[tiers == "Slow"].index

    selected_fast = select_top_n(scores, fast_names, fast_needed)
    selected_medium = select_top_n(scores, medium_names, medium_needed)
    selected_slow = select_top_n(scores, slow_names, slow_needed)

    fast_days = place_fast_movers(selected_fast, peak_days)
    other_days = place_other_movers(selected_medium, selected_slow)

    schedule = {day: [] for day in range(1, CYCLE_DAYS + 1)}
    for name, day in fast_days.items():
        schedule[day].append({
            "name": name,
            "velocity": "Fast",
            "recency_score": float(scores[name]),
        })
    for name, day in other_days.items():
        schedule[day].append({
            "name": name,
            "velocity": tiers[name],
            "recency_score": float(scores[name]),
        })
    return schedule


def validate_schedule(schedule):
    all_names = [p["name"] for products in schedule.values() for p in products]
    assert len(all_names) == len(set(all_names)), "Duplicate product found across the 31-day cycle!"
    for day, products in schedule.items():
        assert len(products) == TOTAL_SLOTS_PER_DAY, f"Day {day} has {len(products)} products, expected {TOTAL_SLOTS_PER_DAY}"
    return all_names


def main():
    df = load_and_clean_data()
    df = filter_last_3_years(df)

    monthly = compute_monthly_quantities(df)
    scores, anchor_month = compute_recency_scores(monthly)
    tiers = assign_velocity_tiers(scores)

    fast_names = tiers[tiers == "Fast"].index
    peak_days = compute_peak_days(df, fast_names)

    schedule = build_schedule(scores, tiers, peak_days)
    all_names = validate_schedule(schedule)

    print(f"\nAnchor month (most recent month in data): {anchor_month}")
    print(f"Total products scored: {len(scores)}")
    print(f"Tier sizes - Fast: {(tiers == 'Fast').sum()}, Medium: {(tiers == 'Medium').sum()}, Slow: {(tiers == 'Slow').sum()}")
    print(f"Total scheduled slots: {len(all_names)} (unique: {len(set(all_names))})")
    print("Validation passed: no duplicates, 50 products/day across all 31 days")

    print("\nSample - Day 1:")
    for p in schedule[1][:5]:
        print(f"  {p['name']} ({p['velocity']}, score={p['recency_score']:.2f})")


if __name__ == "__main__":
    main()
