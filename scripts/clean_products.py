"""
Loads the raw purchase data, removes row-level junk (exact duplicate
rows, zero/negative quantities, known non-product entries), and cleans
up product names so the same drug isn't split across multiple
inconsistent spellings.

Real billing data enters the same product inconsistently over the
years (e.g. "PARACETAMOL 500MG" vs "PARACETAMOL 500 MG" vs
"Paracetamol-500mg"). Left unfixed this splits one product's purchase
history across multiple "different" products, weakening both the
recency score and the seasonal index.

Two layers of name cleaning:
  Layer 1 — automated, always applied (whitespace/case/punctuation/
            abbreviation normalisation). Safe because it can't change
            which drug a name refers to.
  Layer 2 — fuzzy match, NEVER auto-merged. Flags likely duplicates
            into possible_duplicates.csv for manual review, because
            two similar-looking names can be genuinely different
            products (e.g. "TELPRES 40" vs "TELPRES 40 AM" are
            different drugs).

Usage:
    python scripts/clean_products.py
"""

import glob
import os
import re

import pandas as pd
from rapidfuzz import fuzz, process

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "possible_duplicates.csv")

# Known non-product entries that appear in the billing export but are
# not actual medicines (e.g. service/consultation charges).
NON_PRODUCT_NAMES = {"FEE"}

# Common abbreviation standardisation — extend this dict as new
# inconsistent forms are discovered in future monthly exports.
ABBREVIATIONS = {
    r"\bTABLETS?\b": "TAB",
    r"\bTABS\b": "TAB",
    r"MG\.": "MG",
}

FUZZY_THRESHOLD = 85

# Optional manual mapping for genuine duplicates found via the fuzzy
# review (old_name -> correct_name), e.g. produced by reviewing
# possible_duplicates.csv. Applied only if the file exists; absent by
# default, since no merges have been confirmed yet.
MAPPING_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "name_mapping.csv")


def load_raw_data():
    # Monthly retrain exports sometimes come back as legacy .xls
    # (e.g. POS "export to Excel") instead of .xlsx -- glob for both
    # so a differently-formatted export isn't silently skipped.
    paths = sorted(
        glob.glob(os.path.join(RAW_DIR, "*.xlsx"))
        + glob.glob(os.path.join(RAW_DIR, "*.xls"))
    )
    frames = [pd.read_excel(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def remove_duplicate_rows(df):
    before = len(df)
    df = df.drop_duplicates(subset=["Product Name", "Date", "Qty."])
    print(f"Removed {before - len(df)} exact duplicate rows (same product/date/qty)")
    return df


def remove_invalid_quantities(df):
    before = len(df)
    df = df[df["Qty."] > 0]
    print(f"Removed {before - len(df)} rows with zero/negative quantity")
    return df


def exclude_non_products(df):
    before = len(df)
    is_non_product = df["Product Name"].str.strip().str.upper().isin(NON_PRODUCT_NAMES)
    df = df[~is_non_product]
    print(f"Removed {before - len(df)} rows for known non-product entries: {NON_PRODUCT_NAMES}")
    return df


def normalize_name(name):
    name = name.strip().upper()
    name = re.sub(r"\s+", " ", name)          # collapse multiple spaces
    name = re.sub(r"[.,\-]+$", "", name).strip()  # trailing punctuation
    for pattern, replacement in ABBREVIATIONS.items():
        name = re.sub(pattern, replacement, name)
    return name


def apply_layer1_cleaning(df):
    df = df.copy()
    df["clean_name"] = df["Product Name"].apply(normalize_name)
    return df


def find_possible_duplicates(df, threshold=FUZZY_THRESHOLD):
    """Layer 2 — fuzzy-match the Layer-1-cleaned names. Returns pairs
    for manual review; nothing here is merged automatically."""
    qty_by_name = df.groupby("clean_name")["Qty."].sum()
    names = qty_by_name.index.tolist()

    scores = process.cdist(names, names, scorer=fuzz.ratio)

    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            score = scores[i][j]
            if score >= threshold:
                pairs.append({
                    "Product A": names[i],
                    "Product B": names[j],
                    "Similarity %": round(float(score), 1),
                    "Qty A": int(qty_by_name[names[i]]),
                    "Qty B": int(qty_by_name[names[j]]),
                })

    return pd.DataFrame(pairs).sort_values("Similarity %", ascending=False)


def apply_manual_mapping(df, mapping_path=MAPPING_PATH):
    """Applies a manually-reviewed old_name -> correct_name mapping
    (columns: old_name, correct_name), if one has been provided.
    No-op if the mapping file doesn't exist yet."""
    if not os.path.exists(mapping_path):
        return df
    mapping = pd.read_csv(mapping_path)
    name_map = dict(zip(mapping["old_name"], mapping["correct_name"]))
    df = df.copy()
    df["clean_name"] = df["clean_name"].replace(name_map)
    return df


def load_and_clean_data():
    """Entry point used by algorithm.py — runs all row-level and
    Layer 1 name cleaning, returns the cleaned dataframe."""
    df = load_raw_data()
    df = remove_duplicate_rows(df)
    df = remove_invalid_quantities(df)
    df = exclude_non_products(df)
    df = apply_layer1_cleaning(df)
    df = apply_manual_mapping(df)
    return df


def main():
    df = load_and_clean_data()

    print(f"\nUnique names before Layer 1 cleaning: {df['Product Name'].nunique()}")
    print(f"Unique names after Layer 1 cleaning: {df['clean_name'].nunique()}")

    possible_dupes = find_possible_duplicates(df)
    possible_dupes.to_csv(OUTPUT_PATH, index=False)
    print(f"\nFound {len(possible_dupes)} possible duplicate pairs (similarity >= {FUZZY_THRESHOLD}%)")
    print(f"Written to {OUTPUT_PATH} - review manually, do not auto-merge")


if __name__ == "__main__":
    main()
