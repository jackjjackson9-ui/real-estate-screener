@echo off
REM Refresh Redfin Listings — double-click launcher.
REM
REM Prereqs (one-time):
REM   1. Claude Code installed (https://claude.com/claude-code)
REM   2. Claude in Chrome extension installed and connected
REM   3. Logged into redfin.com in that Chrome
REM   4. scripts/markets.json has your saved-search URLs filled in
REM
REM What this does:
REM   Opens Claude Code in the project folder with the /refresh-redfin
REM   command pre-loaded. Claude drives your Chrome through each saved
REM   Redfin search and downloads CSVs into data/listings/.

cd /d "%~dp0"

echo.
echo ============================================================
echo  NJ Rental Screener - Refresh Redfin Listings
echo ============================================================
echo.
echo Before continuing, make sure:
echo   - Chrome is open
echo   - The Claude in Chrome extension shows "connected"
echo   - You are logged into redfin.com
echo.
pause

claude "/refresh-redfin"

echo.
echo ============================================================
echo  Done. Next step:
echo    Open GitHub Desktop and click "Push origin" to upload the
echo    new CSVs. Your web app will pick them up automatically.
echo ============================================================
echo.
pause
