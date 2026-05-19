# Refresh Redfin Listings (browser playbook)

Use this when you want fresh Redfin CSVs across all target markets. Run via Claude in Chrome.

## Prereqs

1. The [Claude in Chrome](https://chrome.google.com/webstore) extension installed and connected.
2. You're logged into Redfin in that browser (free account is fine).
3. Saved searches exist on Redfin for each market and their URLs are pasted into `scripts/markets.json` under each market's `redfin_url`.

## How to invoke

Open a new Claude Code session in this directory and say:

> Run the refresh_redfin playbook.

Claude will:

1. Load `scripts/markets.json` and iterate over markets where `redfin_url` is set.
2. For each market: navigate to the saved search, scroll the listings panel to load all results, then click the **Download All** link at the bottom of the list.
3. Save the downloaded CSV to `data/listings/redfin_<market_name>_<YYYY-MM-DD>.csv`, overwriting any prior dump for the same market and date.
4. Move on. If a market hits a CAPTCHA or login prompt, Claude pauses and asks you to solve it before continuing.

## Manual fallback (no extension)

If you don't have the browser extension available, do this for each market:

1. Open the saved search URL in your normal browser.
2. Scroll listings to load all results.
3. Click **Download All** at the bottom.
4. Drop the downloaded CSV into `data/listings/`.

## Setting up the saved searches

For each market in `markets.json`, do this on Redfin once:

1. Go to redfin.com and search the market (use the `label` as a hint for which towns).
2. Apply filters: price range, beds, property type. Match what you have in `markets.json` -> `default_filters` for consistency, or customize per market.
3. Click **Save Search** so the URL becomes a stable saved-search URL.
4. Copy the URL from your browser and paste it into the `redfin_url` field for that market in `markets.json`.

> Redfin limits exports to ~350 rows per CSV. If a market regularly hits that, split it into sub-markets by price band or town and add them as separate entries.
