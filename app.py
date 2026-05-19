"""NJ rental-property screener — Streamlit dashboard (cloud-ready).

Run locally:  streamlit run app.py
Cloud deploy: see DEPLOY.md
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from screener.ingest import load_listings
from screener.rent import load_rent_table, attach_rent_estimate
from screener.underwriting import UnderwritingParams, underwrite, equity_projection

ROOT = Path(__file__).parent
LISTINGS_DIR = ROOT / "data" / "listings"
RENT_TABLE = ROOT / "data" / "rent_psf_by_zip.csv"

st.set_page_config(page_title="NJ Rental Screener", layout="wide", page_icon="🏠")

# ---------- Browser-local persistence ----------
# Stars + rent overrides live in your browser, not on the server. So clearing
# browser data clears them; but it also means they're truly yours, no DB needed.
try:
    from streamlit_local_storage import LocalStorage
    _ls = LocalStorage()
except Exception:
    _ls = None


def _browser_get(key: str):
    if not _ls:
        return st.session_state.get(f"_local_{key}")
    val = _ls.getItem(key)
    if val in (None, "null", ""):
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


def _browser_set(key: str, value):
    if not _ls:
        st.session_state[f"_local_{key}"] = value
        return
    _ls.setItem(key, json.dumps(value))


# ---------- Data loading (cached) ----------

@st.cache_data(show_spinner=False)
def _load(listings_sentinel: float, rent_sentinel: float, overrides_json: str) -> pd.DataFrame:
    listings = load_listings(LISTINGS_DIR)
    if listings.empty:
        return listings
    rent_table = load_rent_table(RENT_TABLE) if RENT_TABLE.exists() else pd.DataFrame(
        columns=["zip", "rent_psf_monthly"]
    )
    # Apply overrides on top of the data-source rent table
    overrides = json.loads(overrides_json) if overrides_json else {}
    if overrides and not rent_table.empty:
        rent_table = rent_table.copy()
        rent_table["zip"] = rent_table["zip"].astype(str).str.zfill(5)
        for zp, val in overrides.items():
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if zp in set(rent_table["zip"]):
                rent_table.loc[rent_table["zip"] == zp, "rent_psf_monthly"] = val
            else:
                rent_table = pd.concat(
                    [rent_table, pd.DataFrame([{"zip": zp, "rent_psf_monthly": val}])],
                    ignore_index=True,
                )
    return attach_rent_estimate(listings, rent_table)


def _dir_mtime(p: Path) -> float:
    if not p.exists():
        return 0.0
    return max((f.stat().st_mtime for f in p.glob("*.csv")), default=0.0)


# ---------- Sidebar: refresh + underwriting + filters ----------

st.sidebar.header("Refresh")
if st.sidebar.button("🔄 Refresh rent data", use_container_width=True,
                      help="Pulls latest Zillow ZORI. For fresh listings, run the Refresh Redfin shortcut on your desktop."):
    with st.spinner("Refreshing rent table…"):
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "refresh_rent_table.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
    st.cache_data.clear()
    if r.returncode == 0:
        st.sidebar.success("Rent data refreshed.")
    else:
        st.sidebar.error(f"Rent refresh failed: {r.stderr[-300:]}")
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Underwriting assumptions")
down_pct = st.sidebar.slider("Down payment %", 0.0, 1.0, 0.25, 0.01)
rate = st.sidebar.slider("Mortgage rate %", 0.0, 0.15, 0.07, 0.0025, format="%.4f")
term_years = st.sidebar.slider("Term (years)", 10, 40, 30, 5)
closing_pct = st.sidebar.slider("Closing costs %", 0.0, 0.05, 0.02, 0.005)
tax_pct = st.sidebar.slider("Property tax % (annual)", 0.0, 0.05, 0.022, 0.001,
                            help="NJ averages ~2.2%; varies a lot by town.")
insurance_pct = st.sidebar.slider("Insurance % (annual)", 0.0, 0.02, 0.005, 0.001)
vacancy_pct = st.sidebar.slider("Vacancy %", 0.0, 0.30, 0.05, 0.01)
maintenance_pct = st.sidebar.slider("Maintenance % of rent", 0.0, 0.30, 0.08, 0.01)
mgmt_pct = st.sidebar.slider("Management % of rent", 0.0, 0.20, 0.08, 0.01)
appreciation_pct = st.sidebar.slider("Appreciation % (annual)", 0.0, 0.10, 0.03, 0.005)
rent_growth_pct = st.sidebar.slider("Rent growth % (annual)", 0.0, 0.10, 0.02, 0.005)
hold_years = st.sidebar.slider("Projection horizon (years)", 1, 30, 10, 1)

params = UnderwritingParams(
    down_pct=down_pct, rate=rate, term_years=term_years, closing_pct=closing_pct,
    tax_pct=tax_pct, insurance_pct=insurance_pct, vacancy_pct=vacancy_pct,
    maintenance_pct=maintenance_pct, mgmt_pct=mgmt_pct,
    appreciation_pct=appreciation_pct, rent_growth_pct=rent_growth_pct,
)

# Load favorites + rent overrides from browser storage
favorites: set[str] = set(_browser_get("favorites") or [])
rent_overrides: dict = _browser_get("rent_overrides") or {}

# ---------- Main panel ----------

st.title("🏠 NJ Rental Screener")

listings = _load(
    _dir_mtime(LISTINGS_DIR),
    RENT_TABLE.stat().st_mtime if RENT_TABLE.exists() else 0.0,
    json.dumps(rent_overrides, sort_keys=True),
)

if listings.empty:
    st.info(
        "👋 **No listings loaded yet.** To populate the dashboard, run the "
        "**Refresh Redfin** desktop shortcut on your PC. It downloads fresh "
        "Redfin CSVs into `data/listings/`. Then sync them up via GitHub Desktop and this app will fill in."
    )
    st.caption("Once data is in, this message will be replaced by the dashboard.")
    st.stop()

scored = underwrite(listings, params)

# Filter widgets
st.sidebar.divider()
st.sidebar.header("Filters")
cities = sorted([c for c in scored["city"].dropna().unique() if isinstance(c, str)])
selected_cities = st.sidebar.multiselect("City", cities, default=cities)

min_p, max_p = int(scored["price"].min(skipna=True) or 0), int(scored["price"].max(skipna=True) or 0)
if max_p > min_p:
    price_range = st.sidebar.slider("Price range ($)", min_p, max_p, (min_p, max_p), step=10_000)
else:
    price_range = (min_p, max_p)

min_beds = st.sidebar.number_input("Min beds", 0, 10, 0)
min_sqft = st.sidebar.number_input("Min sqft", 0, 20_000, 0, step=100)
min_cap = st.sidebar.slider("Min cap rate", -0.05, 0.20, 0.0, 0.005, format="%.3f")
min_coc = st.sidebar.slider("Min cash-on-cash", -0.20, 0.30, -0.20, 0.005, format="%.3f")
only_stars = st.sidebar.checkbox("Show only ★ starred")
hide_missing_rent = st.sidebar.checkbox("Hide listings with no rent estimate", value=True)

mask = (
    scored["city"].isin(selected_cities)
    & scored["price"].between(*price_range)
    & (scored["beds"].fillna(0) >= min_beds)
    & (scored["sqft"].fillna(0) >= min_sqft)
    & (scored["cap_rate"].fillna(-1) >= min_cap)
    & (scored["coc"].fillna(-1) >= min_coc)
)
if hide_missing_rent:
    mask &= scored["monthly_rent"].notna()
if only_stars:
    mask &= scored["listing_id"].isin(favorites)

filtered = scored[mask].copy().sort_values("cap_rate", ascending=False, na_position="last")

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Listings shown", f"{len(filtered):,} / {len(scored):,}")
c2.metric("Median cap rate", f"{filtered['cap_rate'].median():.2%}" if not filtered.empty else "—")
c3.metric("Median CoC", f"{filtered['coc'].median():.2%}" if not filtered.empty else "—")
c4.metric("★ Starred", f"{len(favorites):,}")

# ---------- Tabs ----------

tab_listings, tab_map, tab_equity, tab_rent = st.tabs(
    ["📋 Listings", "🗺️ Map", "📈 Equity build", "💰 Rent assumptions"]
)

with tab_map:
    map_df = filtered.dropna(subset=["lat", "lon"]).copy()
    if map_df.empty:
        st.caption("No mappable listings.")
    else:
        def _color(c):
            if pd.isna(c): return [128, 128, 128, 160]
            if c >= 0.07: return [34, 197, 94, 200]
            if c >= 0.05: return [234, 179, 8, 200]
            return [239, 68, 68, 200]
        map_df["_color"] = map_df["cap_rate"].apply(_color)
        map_df["_price_str"] = map_df["price"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
        map_df["_cap_str"] = map_df["cap_rate"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "—")
        map_df["_rent_str"] = map_df["monthly_rent"].apply(lambda x: f"${x:,.0f}/mo" if pd.notna(x) else "—")
        layer = pdk.Layer(
            "ScatterplotLayer", data=map_df,
            get_position=["lon", "lat"], get_fill_color="_color",
            get_radius=120, radius_min_pixels=4, radius_max_pixels=14, pickable=True,
        )
        view = pdk.ViewState(latitude=map_df["lat"].mean(), longitude=map_df["lon"].mean(), zoom=10)
        tooltip = {
            "html": "<b>{address}</b><br/>{city}, {zip}<br/>Price: {_price_str}<br/>"
                    "Cap: {_cap_str}<br/>Rent: {_rent_str}<br/>{beds} bd / {baths} ba / {sqft} sqft",
            "style": {"backgroundColor": "white", "color": "black"},
        }
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip,
                                  map_style="mapbox://styles/mapbox/light-v9"))
        st.caption("🟢 ≥ 7% cap | 🟡 5–7% | 🔴 < 5% | ⚫ unknown")

with tab_listings:
    display_cols = [
        "listing_id", "address", "city", "zip", "price", "beds", "baths", "sqft",
        "monthly_rent", "rent_source", "cap_rate", "coc",
        "monthly_cash_flow", "annual_cash_flow", "cash_invested",
        "dom", "year_built", "url",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]
    table = filtered[display_cols].copy()
    table.insert(0, "★", table["listing_id"].isin(favorites))

    edited = st.data_editor(
        table, use_container_width=True, height=520, hide_index=True,
        disabled=[c for c in table.columns if c != "★"],
        column_config={
            "★": st.column_config.CheckboxColumn("★", help="Star to save"),
            "url": st.column_config.LinkColumn("Listing", display_text="open"),
            "price": st.column_config.NumberColumn(format="$%d"),
            "monthly_rent": st.column_config.NumberColumn(format="$%.0f"),
            "monthly_cash_flow": st.column_config.NumberColumn(format="$%.0f"),
            "annual_cash_flow": st.column_config.NumberColumn(format="$%.0f"),
            "cash_invested": st.column_config.NumberColumn(format="$%.0f"),
            "cap_rate": st.column_config.NumberColumn(format="%.2f%%",
                                                       help="NOI / price (unlevered)"),
            "coc": st.column_config.NumberColumn(format="%.2f%%",
                                                  help="Year-1 cash flow / cash invested"),
            "sqft": st.column_config.NumberColumn(format="%d"),
            "dom": st.column_config.NumberColumn("DOM", format="%d"),
        },
        key="listings_editor",
    )
    new_favs = set(edited.loc[edited["★"], "listing_id"])
    if new_favs != favorites:
        favorites = new_favs
        _browser_set("favorites", sorted(favorites))

with tab_equity:
    options = filtered["listing_id"].tolist()
    if not options:
        st.caption("No listings to project.")
    else:
        labels = {
            row["listing_id"]: f'{row.get("address", "?")}, {row.get("city", "?")} — ${row["price"]:,.0f}'
            for _, row in filtered.iterrows()
        }
        selected = st.selectbox("Pick a listing", options, format_func=lambda i: labels.get(i, i))
        row = filtered.loc[filtered["listing_id"] == selected].iloc[0]
        proj = equity_projection(row["price"], row.get("monthly_rent", np.nan), params, hold_years)
        if proj.empty:
            st.caption("Not enough data to project.")
        else:
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.line_chart(proj.set_index("year")[["equity", "loan_balance", "property_value"]])
            with col_b:
                final = proj.iloc[-1]
                st.metric(f"Equity in year {hold_years}", f"${final['equity']:,.0f}")
                st.metric("Cumulative cash flow", f"${final['cumulative_cash_flow']:,.0f}")
                st.metric("Total return over basis", f"${final['total_return']:,.0f}")
            with st.expander("Year-by-year detail"):
                st.dataframe(proj.style.format({
                    "property_value": "${:,.0f}", "loan_balance": "${:,.0f}", "equity": "${:,.0f}",
                    "annual_cash_flow": "${:,.0f}", "cumulative_cash_flow": "${:,.0f}",
                    "total_return": "${:,.0f}",
                }), use_container_width=True)

with tab_rent:
    st.caption(
        "Rent values come from Zillow ZORI (auto-refreshed). Add an **override** to use your "
        "own number for any ZIP — overrides live in your browser and apply on every load."
    )
    if RENT_TABLE.exists():
        base = pd.read_csv(RENT_TABLE, dtype={"zip": str})
        base["zip"] = base["zip"].astype(str).str.zfill(5)
    else:
        base = pd.DataFrame(columns=["zip", "rent_psf_monthly", "town", "source", "last_updated", "notes"])
    base["override"] = base["zip"].map(lambda z: rent_overrides.get(z))
    base["effective"] = base.apply(
        lambda r: r["override"] if pd.notna(r.get("override")) else r["rent_psf_monthly"], axis=1
    )

    visible_cols = ["zip", "town", "rent_psf_monthly", "override", "effective", "source", "last_updated"]
    visible_cols = [c for c in visible_cols if c in base.columns]
    rent_edit = st.data_editor(
        base[visible_cols], use_container_width=True, height=420, hide_index=True,
        disabled=[c for c in visible_cols if c != "override"],
        column_config={
            "rent_psf_monthly": st.column_config.NumberColumn("Data source $/sqft", format="$%.2f", disabled=True),
            "override": st.column_config.NumberColumn("Your override $/sqft", format="$%.2f",
                                                       help="Leave blank to use the data-source value"),
            "effective": st.column_config.NumberColumn("Used $/sqft", format="$%.2f", disabled=True),
        },
        key="rent_editor",
    )
    new_overrides = {}
    for _, r in rent_edit.iterrows():
        if pd.notna(r.get("override")):
            new_overrides[str(r["zip"]).zfill(5)] = float(r["override"])
    if new_overrides != rent_overrides:
        _browser_set("rent_overrides", new_overrides)
        st.success("Override saved. Refresh the page to apply to listings.")

with st.expander("Notes & caveats"):
    st.markdown("""
- Rent values feed from Zillow ZORI by ZIP, converted to $/sqft using assumed unit sizes.
  Your overrides win when set.
- NJ property tax varies meaningfully by town — slider is a single rate. Verify per-deal.
- Stars & rent overrides live in **your browser** (localStorage). Clearing browser data clears them.
- Listings refresh once a day via a scheduled job, plus on-demand via **Refresh now**.
""")
