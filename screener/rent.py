"""Rent estimation: per-listing override column wins, else ZIP $/sqft table."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_rent_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"zip": str})
    df["zip"] = df["zip"].astype(str).str.zfill(5)
    df["rent_psf_monthly"] = pd.to_numeric(df["rent_psf_monthly"], errors="coerce")
    return df[["zip", "rent_psf_monthly"]]


def attach_rent_estimate(listings: pd.DataFrame, rent_table: pd.DataFrame) -> pd.DataFrame:
    """Add monthly_rent + rent_source columns to listings.

    Priority: rent_estimate column on the row (if numeric & > 0) wins.
    Fallback: rent_psf_monthly[zip] * sqft.
    Anything that can't be resolved gets monthly_rent = NaN and rent_source = 'missing'.
    """
    df = listings.merge(rent_table, on="zip", how="left")

    override = df.get("rent_estimate")
    fallback = df["rent_psf_monthly"] * df["sqft"]

    if override is not None:
        has_override = override.notna() & (override > 0)
        df["monthly_rent"] = override.where(has_override, fallback)
        df["rent_source"] = has_override.map({True: "override", False: "zip_table"})
    else:
        df["monthly_rent"] = fallback
        df["rent_source"] = "zip_table"

    df.loc[df["monthly_rent"].isna(), "rent_source"] = "missing"
    return df
