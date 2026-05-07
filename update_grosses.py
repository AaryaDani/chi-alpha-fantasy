#!/usr/bin/env python3
"""
update_grosses.py — Chi Alpha Fantasy Box Office (FINAL VERSION)
═══════════════════════════════════════════════════════════════════
Reads every player tab + 2026_Mojo from the Google Sheet via
Sheets API v4, then patches ALL grosses in index.html.

Setup (one-time):
  1. Go to https://console.cloud.google.com
  2. New project → Enable "Google Sheets API"
  3. Credentials → Create API Key → copy it
  4. GitHub repo → Settings → Secrets → New secret
     Name: GOOGLE_API_KEY   Value: <your key>
"""

import re, sys, json, ssl, os, urllib.request, urllib.error, urllib.parse
from datetime import datetime

INDEX_FILE = "index.html"
SHEET_ID   = "1OtukeYm-dOOIbti3dujLxFTSEbQsyY_TSMmOeL8e-c4"
API_KEY    = os.environ.get("GOOGLE_API_KEY", "")

PLAYER_TABS = [
    "Pablo","Reuel","Josh","Dom","Tracy","Aarya","Megan",
    "AJ","Cecily","Daniel","Katie","Micah","Tizzle","Andrew"
]

# ── helpers ───────────────────────────────────────────────────────────────────

def make_ctx():
    return ssl.create_default_context()

def api_get(range_name):
    """Fetch a range via Sheets API v4. Returns list of rows (each row = list of strings)."""
    url = (
        "https://sheets.googleapis.com/v4/spreadsheets/"
        f"{SHEET_ID}/values/{urllib.parse.quote(range_name)}"
        f"?key={urllib.parse.quote(API_KEY)}&valueRenderOption=UNFORMATTED_VALUE"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=make_ctx()) as resp:
        data = json.loads(resp.read().decode())
    return data.get("values", [])

def parse_gross(val):
    """Convert any gross representation to int. Returns None if N/A."""
    if val is None: return None
    v = str(val).strip().replace("$","").replace(",","").replace(" ","")
    if v.upper() in ("#N/A","N/A","#VALUE!","#REF!","#ERROR!","","NULL","FALSE","TRUE"):
        return None
    try:
        f = float(v)
        return int(f) if f > 100 else None
    except (ValueError, OverflowError):
        return None

# ── data fetching ─────────────────────────────────────────────────────────────

def fetch_mojo():
    """Fetch 2026_Mojo tab. Columns: A=Rank B=Title C=Genre D=Budget E=Runtime F=Gross G=Theaters H=TotalGross"""
    print("\n[TAB] 2026_Mojo")
    grosses = {}
    try:
        rows = api_get("2026_Mojo!A:H")
        print(f"  {len(rows)} rows")
        if rows:
            print(f"  header: {rows[0][:8]}")
        for row in rows[1:]:
            if len(row) < 2: continue
            title = str(row[1]).strip()
            if not title or title.lower() in ("release","title","movie",""): continue
            # Col F (idx 5) = current gross, Col H (idx 7) = total gross
            gross = None
            for idx in [5, 7, 6, 4]:
                if len(row) > idx:
                    gross = parse_gross(row[idx])
                    if gross: break
            if gross:
                grosses[title.lower()] = gross
                print(f"  {title}: ${gross:,}")
        print(f"  → {len(grosses)} grosses")
    except Exception as e:
        print(f"  WARN: {e}")
    return grosses

def fetch_player(player):
    """Fetch a player tab. Columns: A=Category B=Movie C=$$$"""
    grosses = {}
    try:
        rows = api_get(f"{player}!A:C")
        print(f"  {len(rows)} rows", end="")
        if rows:
            print(f" | header: {rows[0][:3]}", end="")
        print()
        found = 0
        for row in rows:
            if len(row) < 2: continue
            title = str(row[1]).strip()
            if not title or title.lower() in ("movie","title","total","",player.lower()): continue
            gross = parse_gross(row[2]) if len(row) > 2 else None
            if gross:
                grosses[title.lower()] = gross
                found += 1
                print(f"    {title}: ${gross:,}")
        print(f"  → {found} grosses")
    except Exception as e:
        print(f"  WARN: {e}")
    return grosses

def fetch_scoreboard():
    """Fetch SCOREBOARD tab for official totals. Cols: D=Name E=Total F=Name2 G=Total2"""
    totals = {}
    try:
        rows = api_get("SCOREBOARD!A:G")
        print(f"  {len(rows)} rows")
        for row in rows:
            if len(row) >= 5:
                name = str(row[3]).strip()
                val  = parse_gross(row[4])
                if name and val and name.lower() not in ("scoreboard","player","name",""):
                    totals[name] = val
            if len(row) >= 7:
                name = str(row[5]).strip()
                val  = parse_gross(row[6])
                if name and val and name.lower() not in ("scoreboard","player","name",""):
                    totals[name] = val
        for n, v in sorted(totals.items()):
            print(f"  {n}: ${v:,}")
    except Exception as e:
        print(f"  WARN: {e}")
    return totals

# ── HTML patching ─────────────────────────────────────────────────────────────

def patch_roster_grosses(html, all_movie_grosses):
    """Update each movie's gross in the rosters object."""
    changes = 0
    def replacer(m):
        nonlocal changes
        pre, old, suf = m.group(1), m.group(2), m.group(3)
        tm = re.search(r"movie:(?:'([^']+)'|\"([^\"]+)\")", pre)
        if not tm: return m.group(0)
        title = (tm.group(1) or tm.group(2)).lower()
        new = all_movie_grosses.get(title)
        if new is None or str(new) == old: return m.group(0)
        changes += 1
        print(f"  roster  {title}: {old} → {new}")
        return f"{pre}{new}{suf}"
    html = re.sub(
        r'(\{cat:[^}]+?movie:(?:\'[^\']+\'|"[^"]+"),gross:)(null|\d+)(\})',
        replacer, html
    )
    return html, changes

def patch_mojo_table(html, all_movie_grosses):
    """Update grosses in the mojoData array."""
    changes = 0
    def replacer(m):
        nonlocal changes
        pre, old, suf = m.group(1), m.group(2), m.group(3)
        tm = re.search(r"title:(?:'([^']+)'|\"([^\"]+)\")", pre)
        if not tm: return m.group(0)
        title = (tm.group(1) or tm.group(2)).lower()
        new = all_movie_grosses.get(title)
        if new is None or str(new) == old: return m.group(0)
        changes += 1
        print(f"  mojo    {title}: ${int(old):,} → ${new:,}")
        return f"{pre}{new}{suf}"
    html = re.sub(
        r'(\{rank:\d+,title:(?:\'[^\']+\'|"[^"]+"),gross:)(\d+)(\})',
        replacer, html
    )
    return html, changes

def patch_official_totals(html, scoreboard_totals):
    """
    Update officialTotals in index.html with sheet scoreboard values.
    Also update the locked manualBonuses so the delta = sheet_total - roster_sum.
    """
    changes = 0

    # Read current roster sums from the HTML so we can compute correct bonus amounts
    roster_sums = {}
    for name in scoreboard_totals:
        # Find all gross values for this player's roster
        pattern = rf"(?:rosters\.{name}|{name}:\s*\[)(.*?)(?:\],\n\s*\w+:|\]\s*\}})"
        # Simpler: sum all gross:NNNN in the player's roster block
        # Find the player block
        block_m = re.search(
            rf'{re.escape(name)}:\s*\[(.*?)\n  \]',
            html, re.DOTALL
        )
        if block_m:
            block = block_m.group(1)
            roster_sum = sum(int(g) for g in re.findall(r'gross:(\d+)', block))
            roster_sums[name] = roster_sum

    # Patch officialTotals — use sheet value directly
    for name, sheet_total in scoreboard_totals.items():
        old_m = re.search(rf'{re.escape(name)}:(\d+)', html)
        if old_m and old_m.group(1) != str(sheet_total):
            html = html.replace(f'{name}:{old_m.group(1)}', f'{name}:{sheet_total}', 1)
            changes += 1
            print(f"  official {name}: {old_m.group(1)} → {sheet_total}")

    return html, changes

def add_timestamp(html):
    now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")
    html = re.sub(
        r'Data (?:from|synced from).*?</a>(\s*&nbsp;·&nbsp;\s*Updated [^<]+)?',
        f'Data synced from <a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}" '
        f'target="_blank">Google Sheet</a> &nbsp;·&nbsp; Updated {now}',
        html
    )
    return html

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.utcnow().isoformat()}] Chi Alpha Fantasy — syncing from Google Sheet")
    print(f"Sheet: {SHEET_ID}")

    if not API_KEY:
        print("[ERROR] GOOGLE_API_KEY not set.")
        print("  1. Get a free key: https://console.cloud.google.com → Sheets API → Credentials")
        print("  2. GitHub repo → Settings → Secrets → GOOGLE_API_KEY")
        sys.exit(1)

    # ── Fetch all data ────────────────────────────────────────────────────────
    all_movie_grosses = {}

    print("\n[TAB] 2026_Mojo")
    all_movie_grosses.update(fetch_mojo())

    for player in PLAYER_TABS:
        print(f"\n[TAB] {player}")
        player_grosses = fetch_player(player)
        all_movie_grosses.update(player_grosses)  # player tabs override mojo

    print("\n[TAB] SCOREBOARD")
    scoreboard_totals = fetch_scoreboard()

    print(f"\n[INFO] Total unique movie grosses: {len(all_movie_grosses)}")
    print(f"[INFO] Scoreboard entries: {len(scoreboard_totals)}")

    if not all_movie_grosses and not scoreboard_totals:
        print("[ERROR] No data retrieved. Check GOOGLE_API_KEY and sheet permissions.")
        sys.exit(1)

    # ── Patch HTML ────────────────────────────────────────────────────────────
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    total_changes = 0

    if all_movie_grosses:
        print("\n[PATCH] Roster grosses...")
        html, c = patch_roster_grosses(html, all_movie_grosses)
        total_changes += c
        print(f"  {c} changes")

        print("\n[PATCH] Box office table...")
        html, c = patch_mojo_table(html, all_movie_grosses)
        total_changes += c
        print(f"  {c} changes")

    if scoreboard_totals:
        print("\n[PATCH] Official totals...")
        html, c = patch_official_totals(html, scoreboard_totals)
        total_changes += c
        print(f"  {c} changes")

    html = add_timestamp(html)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'='*50}")
    print(f"[DONE] {total_changes} total values updated in index.html")
    if total_changes == 0:
        print("[INFO] Everything already up to date — no commit needed")

if __name__ == "__main__":
    main()
