#!/usr/bin/env python3
"""
update_grosses.py
Pulls box office data directly from the Chi Alpha Fantasy Google Sheet
and patches index.html with updated grosses.

The Google Sheet must be shared as "Anyone with the link can view".
Sheet ID is hardcoded below — no API key needed.
"""

import re
import sys
import csv
import ssl
import io
import urllib.request
import urllib.error
from datetime import datetime

INDEX_FILE = "index.html"
SHEET_ID   = "1OtukeYm-dOOIbti3dujLxFTSEbQsyY_TSMmOeL8e-c4"

# Sheet tab names to fetch
SHEETS = {
    "SCOREBOARD": None,
    "2026_Mojo":  None,
    "Pablo":  None, "Reuel":  None, "Josh":   None, "Dom":    None,
    "Tracy":  None, "Aarya":  None, "Megan":  None, "AJ":     None,
    "Cecily": None, "Daniel": None, "Katie":  None, "Micah":  None,
    "Tizzle": None, "Andrew": None,
}

def make_ctx():
    ctx = ssl.create_default_context()
    return ctx

def fetch_sheet_csv(sheet_name):
    """Fetch a single tab as CSV from a public Google Sheet."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&sheet={urllib.parse.quote(sheet_name)}"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; chi-alpha-fantasy-bot/1.0)"
    })
    with urllib.request.urlopen(req, timeout=20, context=make_ctx()) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")

import urllib.parse

def parse_gross(val):
    """Convert a gross string like '$403,288,805' or '403288805' to int. Returns None if N/A."""
    if not val:
        return None
    v = str(val).strip().replace("$", "").replace(",", "").replace(" ", "")
    if v in ("#N/A", "N/A", "#VALUE!", "#REF!", "", "null"):
        return None
    try:
        f = float(v)
        return int(f) if f > 0 else None
    except ValueError:
        return None

def fetch_all_sheets():
    """Fetch all player sheets and return {player: {movie_title_lower: gross}}"""
    player_names = ["Pablo","Reuel","Josh","Dom","Tracy","Aarya","Megan",
                    "AJ","Cecily","Daniel","Katie","Micah","Tizzle","Andrew"]
    
    all_grosses = {}   # title_lower -> gross (from 2026_Mojo, most authoritative)
    player_data  = {}  # player -> {title_lower -> gross}

    # ── 1. Pull 2026_Mojo tab for the authoritative gross numbers ────────────
    print("[INFO] Fetching 2026_Mojo tab...")
    try:
        csv_text = fetch_sheet_csv("2026_Mojo")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        # Expected columns: Rank, Release, Genre, Budget, Runtime, Gross, Theaters, Total Gross, ...
        # We want col 0 (rank) and col 1 (title) and col 5 (gross) or col 7 (total gross)
        # Find header row
        header = None
        for i, row in enumerate(rows):
            if row and row[0].strip().lower() in ('rank', '1', ''):
                if any('gross' in c.lower() for c in row):
                    header = [c.lower().strip() for c in row]
                    data_start = i + 1
                    break
        
        if not header:
            # No header found, assume first row is data: Rank, Title, ..., Gross
            data_start = 1
            
        for row in rows[data_start:]:
            if len(row) < 2:
                continue
            title = row[1].strip() if len(row) > 1 else ""
            if not title or title.lower() in ('release', 'title', ''):
                continue
            # Try column 5 (weekly gross) first, then column 7 (total gross)
            gross = None
            for col_idx in [7, 5, 6]:
                if len(row) > col_idx:
                    gross = parse_gross(row[col_idx])
                    if gross:
                        break
            if title and gross:
                all_grosses[title.lower()] = gross
                print(f"  Mojo: {title} = ${gross:,}")

    except Exception as e:
        print(f"[WARN] Could not fetch 2026_Mojo: {e}")

    # ── 2. Pull each player tab for per-movie grosses ─────────────────────────
    for player in player_names:
        print(f"[INFO] Fetching {player} tab...")
        try:
            csv_text = fetch_sheet_csv(player)
            reader = csv.reader(io.StringIO(csv_text))
            rows = list(reader)
            player_data[player] = {}
            for row in rows:
                if len(row) < 3:
                    continue
                # Rows look like: Category, Movie Title, Gross
                # Skip header/total rows
                title = row[1].strip() if len(row) > 1 else ""
                gross_str = row[2].strip() if len(row) > 2 else ""
                if not title or title.lower() in ('movie', 'title', 'total', ''):
                    continue
                gross = parse_gross(gross_str)
                if gross:
                    player_data[player][title.lower()] = gross
                    all_grosses[title.lower()] = gross
        except Exception as e:
            print(f"[WARN] Could not fetch {player}: {e}")

    return all_grosses, player_data

def patch_html(html, all_grosses):
    """Patch all gross values in index.html based on sheet data."""
    total_changes = 0

    def replace_gross(m):
        nonlocal total_changes
        prefix    = m.group(1)
        title_raw = m.group(2).strip("'\"")
        old_gross = m.group(3)
        suffix    = m.group(4)

        tl = title_raw.lower()
        new_gross = all_grosses.get(tl)

        if new_gross is None:
            return m.group(0)

        new_str = str(new_gross)
        if old_gross == new_str:
            return m.group(0)

        total_changes += 1
        print(f"  ✓ {title_raw}: {old_gross} → {new_str}")
        return f"{prefix}{new_str}{suffix}"

    # Patch rosters: {cat:'...',movie:'Title',gross:VALUE}
    html = re.sub(
        r'(\{cat:[^,]+,movie:(?:\'[^\']+\'|"[^"]+"),gross:)(null|\d+)(\})',
        lambda m: replace_gross_simple(m, all_grosses),
        html
    )

    # Patch mojoData: {rank:N,title:'Title',gross:VALUE}
    html = re.sub(
        r'(\{rank:\d+,title:(?:\'[^\']+\'|"[^"]+"),gross:)(\d+)(\})',
        lambda m: replace_mojo_gross(m, all_grosses),
        html
    )

    return html, total_changes

def replace_gross_simple(m, all_grosses):
    full   = m.group(0)
    prefix = m.group(1)
    old    = m.group(2)
    suffix = m.group(3)

    # Extract title from prefix
    title_m = re.search(r"movie:(?:'([^']+)'|\"([^\"]+)\")", prefix)
    if not title_m:
        return full
    title = (title_m.group(1) or title_m.group(2)).lower()
    new_gross = all_grosses.get(title)
    if new_gross is None or str(new_gross) == old:
        return full
    print(f"  roster  {title}: {old} → {new_gross}")
    return f"{prefix}{new_gross}{suffix}"

def replace_mojo_gross(m, all_grosses):
    full   = m.group(0)
    prefix = m.group(1)
    old    = m.group(2)
    suffix = m.group(3)

    title_m = re.search(r"title:(?:'([^']+)'|\"([^\"]+)\")", prefix)
    if not title_m:
        return full
    title = (title_m.group(1) or title_m.group(2)).lower()
    new_gross = all_grosses.get(title)
    if new_gross is None or str(new_gross) == old:
        return full
    print(f"  mojo    {title}: ${int(old):,} → ${new_gross:,}")
    return f"{prefix}{new_gross}{suffix}"

def add_timestamp(html):
    now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")
    html = re.sub(
        r'Data from.*?The Numbers.*?</a>(\s*&nbsp;·&nbsp;\s*Updated [^<]+)?',
        f'Data from <a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}" '
        f'target="_blank">Google Sheet</a> &nbsp;·&nbsp; Updated {now}',
        html
    )
    return html

def main():
    print(f"[{datetime.utcnow().isoformat()}] Starting gross update from Google Sheet...")

    try:
        all_grosses, player_data = fetch_all_sheets()
    except Exception as e:
        print(f"[ERROR] Failed to fetch sheet data: {e}")
        print("Make sure the Google Sheet is shared as 'Anyone with the link can view'")
        sys.exit(1)

    if not all_grosses:
        print("[ERROR] No gross data retrieved from sheet. Aborting.")
        sys.exit(1)

    print(f"\n[INFO] Got {len(all_grosses)} gross values from sheet")

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    html, changes = patch_html(html, all_grosses)
    html = add_timestamp(html)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[DONE] {changes} values updated in index.html")
    if changes == 0:
        print("[INFO] All values already match the sheet — no changes needed")

if __name__ == "__main__":
    main()
