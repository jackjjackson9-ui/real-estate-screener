# Deploy guide (non-technical version)

You only do this once. After that, the app lives at a URL you bookmark, and you refresh listings by double-clicking a desktop icon.

## What you'll end up with

- A web page at `https://<something>.streamlit.app` that shows your dashboard
- A bookmark on your desktop that opens it in one click
- A second desktop icon called **Refresh Redfin** that pulls fresh listings into the app

## What you need

- Your existing GitHub account
- About 10 minutes

---

## Step 1 — Publish the project to GitHub

You'll use GitHub Desktop (a free visual app — no commands).

1. Download GitHub Desktop: **https://desktop.github.com** → click the purple Download button → run the installer.
2. Open GitHub Desktop. Click **Sign in to GitHub.com** and sign in.
3. Top-left menu: **File → Add Local Repository...**
4. Click **Choose...** and pick `C:\Users\jackj\real-estate-screener`. Click **Add Repository**.
5. In the top toolbar, click **Publish repository**.
6. In the dialog:
   - **Name:** `nj-rental-screener` (or anything you like)
   - **Keep this code private:** ✅ leave checked
   - Click **Publish Repository**.
7. ✅ Done. Your code is now on GitHub.

> Note the GitHub URL — it'll be `https://github.com/<your-username>/nj-rental-screener`. You'll need it in step 2.

---

## Step 2 — Deploy the app on Streamlit Cloud

1. Go to **https://share.streamlit.io** and click **Continue with GitHub** to sign in. Approve the permissions it asks for.
2. Click **New app** (top right).
3. Fill in:
   - **Repository:** pick `<your-username>/nj-rental-screener` from the dropdown
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** optionally customize the subdomain (e.g. `nj-rental-screener`)
4. Click **Deploy!**
5. Wait ~2 minutes while it installs dependencies and starts the app. You'll see logs scrolling — that's normal.
6. When it finishes, you'll land on your live app. Copy the URL from your browser's address bar.

✅ Your app is live.

> The app will show "No listings loaded yet" — that's fine. You'll fix that in step 4.

---

## Step 3 — Put bookmarks on your desktop

### Main app icon

1. Open your live Streamlit URL in Chrome (or your default browser).
2. **Chrome:** click the ⋮ menu → **Cast, save, and share** → **Create shortcut...** → check **Open as window** → **Create**. A desktop icon appears.
   - **Edge:** ⋯ menu → **Apps → Install this site as an app**.
   - **Any browser:** drag the URL from the address bar onto your desktop — creates a `.url` shortcut.
3. ✅ Double-click your new icon. It should open your app.

### Refresh Redfin icon

1. Open File Explorer to `C:\Users\jackj\real-estate-screener`.
2. Right-click `refresh-redfin.bat` → **Send to → Desktop (create shortcut)**.
3. Optionally rename the desktop shortcut to **Refresh Redfin**.
4. (Optional) right-click the shortcut → **Properties → Change Icon...** to pick a nicer icon.

> This shortcut needs [Claude Code](https://claude.com/claude-code) installed and the **Claude in Chrome** extension active. If you don't have those yet, install them now.

---

## Step 4 — Your first Redfin refresh

This is where you seed the app with real listings.

1. **First, paste your saved Redfin search URLs into `scripts/markets.json`.** Open it in any text editor and replace each `"REPLACE_ME"` with the URL of your saved search on Redfin (do a search on Redfin → click **Save Search** → copy the URL).
2. Open Chrome. Make sure you're logged into redfin.com and the Claude in Chrome extension shows **Connected**.
3. Double-click your **Refresh Redfin** desktop icon. A black window opens, Claude walks through each saved search and downloads CSVs. Solve any CAPTCHAs that appear.
4. When done, open **GitHub Desktop**. You'll see the new CSV files in the left panel. Type a message like "fresh listings" at the bottom and click **Commit to main**. Then click **Push origin** at the top.
5. Wait ~30 seconds. Open your web app — it should now show real listings.

---

## Your weekly loop after this

- Double-click your **app icon** anytime to browse.
- When you want fresh listings: double-click **Refresh Redfin** → wait → push from GitHub Desktop → done.
- Rent data refreshes automatically once a day from Zillow.

That's it. Tell me when each step is done and I'll help with anything that breaks.
