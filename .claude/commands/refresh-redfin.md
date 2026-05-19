---
description: Use Claude in Chrome to download Redfin listing CSVs for every market in scripts/markets.json and save them into data/listings/.
---

You are running the Redfin refresh playbook for this project. The user has the
[Claude in Chrome](https://www.anthropic.com/news/claude-in-chrome) extension installed and connected, and is logged into redfin.com in that browser.

Goal: For each market in `scripts/markets.json` whose `redfin_url` is not "REPLACE_ME":

1. Navigate the connected Chrome tab to the market's `redfin_url`.
2. Wait for the listings panel to populate.
3. Scroll the listings list (left/right side panel, not the map) all the way to the bottom so every result is loaded.
4. Find the **Download All** link/button at the very bottom of the listings panel and click it.
5. Capture the downloaded CSV (you may need to ask the user to move it from the default Downloads folder, OR set Chrome's default download path to this project's `data/listings/` first).
6. Rename it to `redfin_<market_name>_<YYYY-MM-DD>.csv` and confirm it's in `data/listings/`.

If a market URL still says `REPLACE_ME`, skip it and tell the user to add the saved-search URL.

If you hit a CAPTCHA or login wall, pause and ask the user to solve it before continuing — don't try to bypass it.

After all markets are processed, summarize: how many CSVs were downloaded, how many listings total, and which markets (if any) failed.

Tip: before starting, check if Chrome's default download directory is set to this project's `data/listings/` folder; if not, ask the user whether to update it for this session.
