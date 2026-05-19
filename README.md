# NJ Rental Screener

Streamlit dashboard that ranks Redfin listings by buy-and-hold rental cash-flow
across your target NJ markets:

- **Monmouth County** (all)
- **Ocean County** subset: Point Pleasant Beach, Point Pleasant Boro, Brick Twp, Bay Head, Mantoloking
- **Hudson County** subset: Jersey City, Hoboken, Weehawken

## Setup

```powershell
cd C:\Users\jackj\real-estate-screener
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Get listings into the app

Two automated paths, plus a manual fallback. Run either or both — duplicates are deduped.

### A) Realtor.com via RapidAPI (unattended)

1. Sign up at [rapidapi.com/apidojo/api/realty-in-us](https://rapidapi.com/apidojo/api/realty-in-us) (free tier ≈ 100 req/mo).
2. Set the env var: `$env:RAPIDAPI_KEY = "your-key-here"`.
3. Run:
   ```powershell
   python scripts/fetch_realtor.py             # all markets
   python scripts/fetch_realtor.py --market hudson_urban
   python scripts/fetch_realtor.py --dry-run   # plan only, no API calls
   ```
4. CSVs land in `data/listings/realtor_<market>_<date>.csv` in Redfin-compatible format.

### B) Redfin via browser automation (Claude in Chrome)

1. Edit `scripts/markets.json` and paste your Redfin saved-search URL into each market's `redfin_url`.
2. Open a new Claude Code session in this folder with the Claude in Chrome extension active.
3. Say: *"Run the refresh_redfin playbook."* Claude drives the browser through each saved search and clicks Download All.

See [scripts/refresh_redfin.md](scripts/refresh_redfin.md) for setup details.

### C) Manual fallback

On Redfin: search a market → scroll to load all results → click **Download All** at the bottom → drop the CSV in `data/listings/`. Same dedupe logic applies.

> Redfin caps each download at ~350 rows. Realtor.com pages 200 at a time, up to ~1000.

## Run

```powershell
streamlit run app.py
```

The app opens at http://localhost:8501.

## Refresh the rent table

`data/rent_psf_by_zip.csv` is the rent-estimate fallback (monthly $/sqft by ZIP).
Refresh it from public data:

```powershell
python scripts/refresh_rent_table.py
```

This pulls **Zillow ZORI** (Observed Rent Index, ZIP-level, smoothed) and converts
to $/sqft using an assumed unit size (900 sqft for urban ZIPs, 1400 sqft suburban).
The previous file is backed up to `rent_psf_by_zip.csv.bak.<date>`.

**For richer data**, also drop a HUD Small Area FMR xlsx at `data/cache/hud_safmr.xlsx`
(download from [huduser.gov](https://www.huduser.gov/portal/datasets/fmr/smallarea/index.html) —
their server requires a real browser session, so this part is manual). The script then
uses HUD as a fallback for any ZIPs Zillow doesn't cover.

You can hand-edit any row in `rent_psf_by_zip.csv` — your edits persist; next refresh
only overwrites rows that have fresh source data. The `source` column tells you which
came from automation vs. manual override.

For per-listing precision, add a `rent_estimate` column directly to a Redfin CSV
(monthly $). When present and > 0, it overrides the ZIP fallback for that listing.

## Underwriting

All assumptions are live sliders in the sidebar:

| Slider | Default |
|---|---|
| Down payment % | 25% |
| Mortgage rate | 7.00% |
| Term (years) | 30 |
| Closing costs % | 2% |
| Property tax % | 2.20% (NJ avg — town-specific in reality) |
| Insurance % | 0.50% |
| Vacancy % | 5% |
| Maintenance (% of rent) | 8% |
| Management (% of rent) | 8% |
| Appreciation | 3% |
| Rent growth | 2% |

**Cap rate** = NOI / price (unlevered).
**Cash-on-cash** = Year-1 cash flow / (down + closing).

## Favorites

Star (`★`) any row in the table; the selection persists to `data/favorites.json`.
Toggle **Show only starred** in the sidebar to focus on your shortlist.

## Map

Markers color-coded by cap rate:
- 🟢 green ≥ 7%
- 🟡 yellow 5–7%
- 🔴 red < 5%
- ⚫ grey unknown (missing rent estimate)

Hover for address, price, cap, rent.

## Equity build

Pick a listing under **Equity build projection** for an N-year chart of:
- Property value (with appreciation)
- Loan balance (real amortization, not straight-line)
- Equity (value − balance)
- Cumulative cash flow + total return over basis

## Files

```
real-estate-screener/
├── app.py                       Streamlit entrypoint
├── requirements.txt
├── screener/
│   ├── ingest.py                Redfin/Realtor CSV loader
│   ├── rent.py                  rent estimation
│   ├── underwriting.py          cap/CoC/equity math
│   └── persistence.py           favorites store
├── scripts/
│   ├── fetch_realtor.py         Realtor.com via RapidAPI
│   ├── refresh_rent_table.py    Zillow ZORI + HUD SAFMR
│   ├── refresh_redfin.md        playbook for browser refresh
│   └── markets.json             target markets, ZIPs, saved-search URLs
└── data/
    ├── listings/                auto-populated; manual drops welcome
    ├── cache/                   downloaded rent-data files
    ├── rent_psf_by_zip.csv      auto-refreshed; hand-edits persist
    └── favorites.json           (auto-managed)
```

## Caveats

- **NJ property taxes** vary a lot by municipality (1.5%–3%+). Single slider is fine for screening; verify per-deal.
- **HOA fees ignored** by design — matters for Hoboken / Jersey City condos.
- **Shore markets are seasonal** — annualized rent assumptions understate gross potential for short-term rentals but overstate stability. Treat the cap rate as a long-term-tenant baseline.
