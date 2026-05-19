"""Refresh data/rent_psf_by_zip.csv from public sources.

Sources, in order of priority per ZIP:
  1. Zillow ZORI (Observed Rent Index, smoothed, SFR+Condo+MFR) — auto-downloaded.
  2. HUD Small Area FMR — auto if accessible, otherwise expects a manually
     downloaded xlsx at data/cache/hud_safmr.xlsx.

For each ZIP in scripts/markets.json:
  - Take Zillow's most recent month's rent value (a $/month for a typical unit).
  - Divide by an assumed typical unit size for the ZIP (urban ZIPs ~900 sqft,
    suburban ~1400 sqft) to get $/sqft monthly.
  - If Zillow has no value for the ZIP, fall back to HUD 2BR FMR / 950 sqft.
  - If neither source has a value, preserve any existing value already in
    rent_psf_by_zip.csv (so user-tuned values aren't wiped).

The output CSV has columns:
  zip, rent_psf_monthly, town, source, last_updated, notes

Usage:
    python scripts/refresh_rent_table.py
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "data" / "rent_psf_by_zip.csv"
MARKETS = ROOT / "scripts" / "markets.json"

ZORI_URL = "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv"
# HUD SAFMR is WAF-protected; we expect a manually downloaded file here:
HUD_FALLBACK_PATH = CACHE / "hud_safmr.xlsx"
HUD_URL_HINT = "https://www.huduser.gov/portal/datasets/fmr/smallarea/index.html"

# Coarse typical unit-size heuristic (sqft) by ZIP. URBAN_ZIPS = high-rise condo/MFR markets.
URBAN_ZIPS = {"07030", "07086", "07302", "07304", "07305", "07306", "07307", "07310", "07311"}
URBAN_SQFT = 900
SUBURBAN_SQFT = 1400


def _http_get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_zori(force: bool = False) -> pd.DataFrame | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / "zori.csv"
    if force or not local.exists():
        try:
            print(f"Downloading Zillow ZORI -> {local.name}")
            local.write_bytes(_http_get(ZORI_URL))
        except Exception as e:
            print(f"  ! Zillow download failed: {e}", file=sys.stderr)
            if not local.exists():
                return None
            print(f"  (using cached {local.name})")
    df = pd.read_csv(local, dtype={"RegionName": str})
    df = df[df["RegionType"] == "zip"].copy()
    month_cols = [c for c in df.columns if c[:4].isdigit() and "-" in c]
    if not month_cols:
        print("  ! ZORI: no month columns found", file=sys.stderr)
        return None
    latest = month_cols[-1]
    df["zip"] = df["RegionName"].str.zfill(5)
    df["zori_rent"] = pd.to_numeric(df[latest], errors="coerce")
    df["zori_month"] = latest
    return df[["zip", "zori_rent", "zori_month"]]


def fetch_hud_safmr() -> pd.DataFrame | None:
    if not HUD_FALLBACK_PATH.exists():
        print(f"  HUD SAFMR file not found at {HUD_FALLBACK_PATH}.")
        print(f"  Manual download: {HUD_URL_HINT}")
        print( "  Save the SAFMR xlsx (any FY) to that path and rerun for richer data.")
        return None
    try:
        df = pd.read_excel(HUD_FALLBACK_PATH)
    except Exception as e:
        print(f"  ! Could not read HUD SAFMR xlsx: {e}", file=sys.stderr)
        return None

    # SAFMR files vary by FY but consistently have a ZIP column and SAFMR_<n>BR columns.
    df.columns = [str(c).strip() for c in df.columns]
    zip_col = next((c for c in df.columns if c.lower() in ("zip", "zip code", "zipcode", "zip_code")), None)
    br2_col = next(
        (c for c in df.columns if "2br" in c.lower().replace(" ", "") and "safmr" in c.lower().replace(" ", "")),
        None,
    ) or next((c for c in df.columns if "2br" in c.lower().replace(" ", "")), None)
    if not zip_col or not br2_col:
        print(f"  ! HUD SAFMR: couldn't locate ZIP / 2BR columns. Found: {list(df.columns)[:10]}...", file=sys.stderr)
        return None

    out = pd.DataFrame({
        "zip": df[zip_col].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(5),
        "hud_2br_rent": pd.to_numeric(df[br2_col], errors="coerce"),
    })
    return out.dropna(subset=["zip"]).drop_duplicates(subset=["zip"])


def load_target_zips() -> dict:
    """zip -> town label, preserving the seed CSV's labels when present."""
    markets = json.loads(MARKETS.read_text(encoding="utf-8"))["markets"]
    target = {}
    for m in markets:
        for z in m["zips"]:
            target[z] = m["label"]
    if OUT.exists():
        existing = pd.read_csv(OUT, dtype={"zip": str})
        if "town" in existing.columns:
            for _, r in existing.iterrows():
                z = str(r["zip"]).zfill(5)
                if z in target and isinstance(r["town"], str) and r["town"].strip():
                    target[z] = r["town"]
    return target


def existing_rows() -> dict:
    if not OUT.exists():
        return {}
    df = pd.read_csv(OUT, dtype={"zip": str})
    return {str(r["zip"]).zfill(5): r.to_dict() for _, r in df.iterrows()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-download cached files")
    args = ap.parse_args(argv)

    target_zips = load_target_zips()
    print(f"Refreshing rent table for {len(target_zips)} target ZIPs")

    zori = fetch_zori(force=args.force)
    hud = fetch_hud_safmr()

    today = date.today().isoformat()
    existing = existing_rows()
    rows = []
    misses = []
    for zp, town in sorted(target_zips.items()):
        rent_psf = None
        source = None
        notes = ""

        if zori is not None:
            match = zori[zori["zip"] == zp]
            if not match.empty and pd.notna(match.iloc[0]["zori_rent"]):
                rent = float(match.iloc[0]["zori_rent"])
                sqft = URBAN_SQFT if zp in URBAN_ZIPS else SUBURBAN_SQFT
                rent_psf = round(rent / sqft, 2)
                source = f"zori:{match.iloc[0]['zori_month']}"
                notes = f"ZORI ${rent:,.0f}/mo / {sqft} sqft assumption"

        if rent_psf is None and hud is not None:
            match = hud[hud["zip"] == zp]
            if not match.empty and pd.notna(match.iloc[0]["hud_2br_rent"]):
                rent_2br = float(match.iloc[0]["hud_2br_rent"])
                rent_psf = round(rent_2br / 950, 2)
                source = "hud_safmr_2br"
                notes = f"HUD SAFMR 2BR ${rent_2br:,.0f}/mo / 950 sqft"

        if rent_psf is None:
            # Preserve any prior value rather than dropping the ZIP.
            prev = existing.get(zp)
            if prev and pd.notna(prev.get("rent_psf_monthly")):
                rent_psf = float(prev["rent_psf_monthly"])
                source = prev.get("source") or "preserved"
                notes = prev.get("notes") or "no fresh data; kept prior value"
            else:
                misses.append(zp)
                continue

        rows.append({
            "zip": zp,
            "rent_psf_monthly": rent_psf,
            "town": town,
            "source": source,
            "last_updated": today,
            "notes": notes,
        })

    df = pd.DataFrame(rows, columns=["zip", "rent_psf_monthly", "town", "source", "last_updated", "notes"])

    if OUT.exists():
        backup = OUT.with_suffix(f".csv.bak.{today}")
        OUT.rename(backup)
        print(f"  backed up previous table -> {backup.name}")
    df.to_csv(OUT, index=False)
    print(f"\nWrote {len(df)} ZIP rows -> {OUT.relative_to(ROOT)}")

    if misses:
        print(f"\n{len(misses)} ZIPs had no data and no prior value (still missing):")
        for z in misses:
            print(f"  {z} — {target_zips[z]}")

    counts = df["source"].value_counts()
    print(f"\nSource breakdown:")
    for src, n in counts.items():
        print(f"  {src}: {n}")


if __name__ == "__main__":
    main()
