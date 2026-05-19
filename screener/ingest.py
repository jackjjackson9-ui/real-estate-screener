"""Load Redfin CSV exports and normalize into a uniform listings DataFrame.

Drop any number of Redfin CSVs into data/listings/ — they are concatenated
and deduped by MLS# (falling back to address).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

REDFIN_COL_MAP = {
    "SALE TYPE": "sale_type",
    "PROPERTY TYPE": "property_type",
    "ADDRESS": "address",
    "CITY": "city",
    "STATE OR PROVINCE": "state",
    "ZIP OR POSTAL CODE": "zip",
    "PRICE": "price",
    "BEDS": "beds",
    "BATHS": "baths",
    "LOCATION": "neighborhood",
    "SQUARE FEET": "sqft",
    "LOT SIZE": "lot_size",
    "YEAR BUILT": "year_built",
    "DAYS ON MARKET": "dom",
    "$/SQUARE FEET": "price_psf",
    "HOA/MONTH": "hoa",
    "STATUS": "status",
    "URL (SEE http://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)": "url",
    "MLS#": "mls",
    "LATITUDE": "lat",
    "LONGITUDE": "lon",
}


def _read_one(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Rename known Redfin columns; pass-through anything else (e.g. user-added rent_estimate)
    rename = {k: v for k, v in REDFIN_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)
    # Normalize any user-added rent override columns
    for variant in ("rent_estimate", "RENT_ESTIMATE", "Rent Estimate", "rent"):
        if variant in df.columns and variant != "rent_estimate":
            df = df.rename(columns={variant: "rent_estimate"})
            break
    df["_source_file"] = path.name
    return df


def load_listings(listings_dir: Path) -> pd.DataFrame:
    """Load and concat every *.csv under listings_dir. Returns empty DF if none found."""
    files = sorted(Path(listings_dir).glob("*.csv"))
    if not files:
        return pd.DataFrame()

    frames = [_read_one(p) for p in files]
    df = pd.concat(frames, ignore_index=True)

    # Coerce numerics
    for col in ("price", "beds", "baths", "sqft", "dom", "price_psf", "lat", "lon", "year_built", "hoa"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "rent_estimate" in df.columns:
        df["rent_estimate"] = pd.to_numeric(df["rent_estimate"], errors="coerce")

    # Normalize zip to 5-digit string (Redfin sometimes drops leading zeros)
    if "zip" in df.columns:
        df["zip"] = df["zip"].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(5)

    # Stable unique key
    df["listing_id"] = df.apply(_listing_id, axis=1)

    # Dedupe: keep first occurrence (in case a listing appears in multiple CSVs)
    df = df.drop_duplicates(subset=["listing_id"], keep="first").reset_index(drop=True)
    return df


def _listing_id(row) -> str:
    mls = str(row.get("mls", "")).strip()
    if mls and mls.lower() not in ("nan", "none", ""):
        return f"mls:{mls}"
    addr = str(row.get("address", "")).strip().lower()
    zp = str(row.get("zip", "")).strip()
    return f"addr:{addr}|{zp}"
