"""Fetch for-sale listings from Realtor.com via RapidAPI ("Realty in US" by apidojo).

Pulls every market in scripts/markets.json and writes one CSV per market to
data/listings/realtor_<market>_<YYYY-MM-DD>.csv in a schema compatible with
the Redfin loader (same column names, so ingest.py picks them up unchanged).

Requirements:
  - Sign up at https://rapidapi.com/apidojo/api/realty-in-us (free tier ≈ 100 req/mo).
  - Set the env var RAPIDAPI_KEY to your key.

Usage:
    python scripts/fetch_realtor.py            # fetch all markets
    python scripts/fetch_realtor.py --market hudson_urban
    python scripts/fetch_realtor.py --dry-run  # report API quota use without writing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MARKETS = ROOT / "scripts" / "markets.json"
LISTINGS_DIR = ROOT / "data" / "listings"

API_HOST = "realty-in-us.p.rapidapi.com"
SEARCH_PATH = "/properties/v3/list"
SEARCH_URL = f"https://{API_HOST}{SEARCH_PATH}"

LIMIT_PER_REQUEST = 200  # Realty-in-US allows up to 200/req on this endpoint.


def _headers() -> dict:
    key = os.environ.get("RAPIDAPI_KEY")
    if not key:
        sys.exit("RAPIDAPI_KEY env var not set. See script docstring.")
    return {
        "x-rapidapi-key": key,
        "x-rapidapi-host": API_HOST,
        "Content-Type": "application/json",
    }


def _post(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(SEARCH_URL, data=data, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_query(location: dict, filters: dict, offset: int = 0, limit: int = LIMIT_PER_REQUEST) -> dict:
    """Construct the v3/list POST body for one city, one page."""
    body = {
        "limit": limit,
        "offset": offset,
        "status": ["for_sale", "ready_to_build"],
        "sort": {"direction": "desc", "field": "list_date"},
        "city": location["city"],
        "state_code": location["state_code"],
    }
    if "min_price" in filters or "max_price" in filters:
        body["list_price"] = {
            "min": filters.get("min_price"),
            "max": filters.get("max_price"),
        }
    if "min_beds" in filters:
        body["beds"] = {"min": filters["min_beds"]}
    if "property_types" in filters:
        body["type"] = filters["property_types"]
    return body


def fetch_city(location: dict, filters: dict, max_pages: int = 5) -> list[dict]:
    """Page through listings for one city until exhausted or max_pages."""
    out = []
    for page in range(max_pages):
        payload = build_query(location, filters, offset=page * LIMIT_PER_REQUEST)
        try:
            resp = _post(payload)
        except Exception as e:
            print(f"    ! API error for {location['city']}: {e}", file=sys.stderr)
            break
        results = (resp.get("data") or {}).get("home_search", {}).get("results") or []
        if not results:
            break
        out.extend(results)
        if len(results) < LIMIT_PER_REQUEST:
            break
        time.sleep(0.6)  # be polite
    return out


def normalize_to_redfin(records: list[dict]) -> pd.DataFrame:
    """Map Realtor.com v3 response objects into Redfin-export column names."""
    rows = []
    for r in records:
        loc = r.get("location") or {}
        addr = loc.get("address") or {}
        coords = (addr.get("coordinate") or {})
        desc = r.get("description") or {}
        prim = r.get("primary_photo") or {}
        rows.append({
            "SALE TYPE": "For Sale",
            "PROPERTY TYPE": (desc.get("type") or "").replace("_", " ").title() or None,
            "ADDRESS": addr.get("line"),
            "CITY": addr.get("city"),
            "STATE OR PROVINCE": addr.get("state_code"),
            "ZIP OR POSTAL CODE": addr.get("postal_code"),
            "PRICE": r.get("list_price"),
            "BEDS": desc.get("beds"),
            "BATHS": desc.get("baths_consolidated") or desc.get("baths"),
            "SQUARE FEET": desc.get("sqft"),
            "LOT SIZE": (desc.get("lot_sqft")),
            "YEAR BUILT": desc.get("year_built"),
            "DAYS ON MARKET": r.get("list_date") and _days_on_market(r["list_date"]) or None,
            "$/SQUARE FEET": (
                round(r["list_price"] / desc["sqft"], 0)
                if r.get("list_price") and desc.get("sqft") else None
            ),
            "HOA/MONTH": (r.get("hoa") or {}).get("fee") if isinstance(r.get("hoa"), dict) else None,
            "STATUS": (r.get("status") or "").replace("_", " ").title() or None,
            "URL (SEE http://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)":
                f"https://www.realtor.com/realestateandhomes-detail/{r.get('property_id')}" if r.get("property_id") else None,
            "MLS#": (r.get("source") or {}).get("listing_id") or r.get("listing_id"),
            "LATITUDE": coords.get("lat"),
            "LONGITUDE": coords.get("lon"),
            "_realtor_property_id": r.get("property_id"),
        })
    return pd.DataFrame(rows)


def _days_on_market(list_date_iso: str) -> int | None:
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(list_date_iso.replace("Z", "+00:00"))
        return max((datetime.now(timezone.utc) - dt).days, 0)
    except Exception:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", help="Fetch only one market by name")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without calling API")
    ap.add_argument("--max-pages", type=int, default=5)
    args = ap.parse_args(argv)

    config = json.loads(MARKETS.read_text(encoding="utf-8"))
    filters = config.get("default_filters", {})
    markets = config["markets"]
    if args.market:
        markets = [m for m in markets if m["name"] == args.market]
        if not markets:
            sys.exit(f"No market named '{args.market}'")

    LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    total_listings = 0

    for m in markets:
        print(f"\n=== {m['name']} — {m['label']} ===")
        if args.dry_run:
            print(f"  would call API for {len(m['realtor_locations'])} cities, up to "
                  f"{len(m['realtor_locations']) * args.max_pages} requests")
            continue

        all_records = []
        for loc in m["realtor_locations"]:
            print(f"  fetching {loc['city']}, {loc['state_code']}...")
            recs = fetch_city(loc, filters, max_pages=args.max_pages)
            print(f"    got {len(recs)} listings")
            all_records.extend(recs)
            time.sleep(0.6)

        if not all_records:
            print("  no listings; skipping write.")
            continue

        df = normalize_to_redfin(all_records)
        # Filter to ZIPs we actually care about (Realtor city search bleeds across ZIPs)
        df = df[df["ZIP OR POSTAL CODE"].astype(str).str.zfill(5).isin(m["zips"])]
        if df.empty:
            print("  all listings outside target ZIPs after filter; skipping.")
            continue

        out_path = LISTINGS_DIR / f"realtor_{m['name']}_{today}.csv"
        df.to_csv(out_path, index=False)
        print(f"  wrote {len(df)} listings -> {out_path.name}")
        total_listings += len(df)

    print(f"\nDone. {total_listings} total listings written to {LISTINGS_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
