"""
EDA — run once to understand the raw purchase data before writing
any algorithm code. Loads every .xlsx in data/raw/, stacks them into
one table, and prints date range, product counts, and data quality
issues (missing values, duplicates, bad quantities, date problems).

Usage:
    python scripts/explore.py
"""

import glob
import os

import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def load_all_raw_files():
    paths = sorted(glob.glob(os.path.join(RAW_DIR, "*.xlsx")))
    frames = []
    for path in paths:
        df = pd.read_excel(path)
        df["source_file"] = os.path.basename(path)
        frames.append(df)
        print(f"Loaded {os.path.basename(path)}: {len(df)} rows")
    combined = pd.concat(frames, ignore_index=True)
    return combined


def main():
    df = load_all_raw_files()

    # Normalise the date column to actual datetimes for comparisons below
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    print("\n=== OVERVIEW ===")
    print(f"Total rows: {len(df)}")
    print(f"Unique products (raw names, untrimmed): {df['Product Name'].nunique()}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")

    print("\n=== TOP 20 PRODUCTS BY TOTAL QUANTITY ===")
    top20 = df.groupby("Product Name")["Qty."].sum().sort_values(ascending=False).head(20)
    print(top20.to_string())

    print("\n=== RECENCY SPLIT ===")
    cutoff = df["Date"].max() - pd.DateOffset(years=3)
    recent = df[df["Date"] >= cutoff]
    older = df[df["Date"] < cutoff]
    print(f"Rows in last 3 years (>= {cutoff.date()}): {len(recent)}")
    print(f"Rows older than 3 years: {len(older)}")

    print("\n=== DATA QUALITY ===")
    missing = df.isna().sum()
    print("Missing values per column:")
    print(missing[missing > 0].to_string() if missing.sum() else "  none")

    dupes = df.duplicated(subset=["Product Name", "Date", "Qty."]).sum()
    print(f"\nExact duplicate rows (same product/date/qty): {dupes}")

    bad_qty = df[df["Qty."] <= 0]
    print(f"\nRows with zero or negative Qty.: {len(bad_qty)}")
    if len(bad_qty):
        print(bad_qty.head(10).to_string())

    unparsed_dates = df["Date"].isna().sum()
    print(f"\nRows where Date failed to parse: {unparsed_dates}")

    # Whitespace / casing inconsistency in product names — relevant for clean_products.py later
    raw_names = df["Product Name"].dropna()
    stripped_dupes = raw_names.nunique() - raw_names.str.strip().str.upper().nunique()
    print(f"\nProduct names that collapse once trimmed+uppercased: {stripped_dupes}")


if __name__ == "__main__":
    main()
