#!/usr/bin/env python3
"""
update_grosses.py - Chi Alpha Fantasy Box Office
Pulls grosses from published Google Sheet (CSV export) and patches index.html.

Column mapping confirmed from spreadsheet:
  2026_Mojo:   A=Rank, B=Title, C=Genre, D=Budget, E=Runtime, F=Gross, G=Theaters, H=Total Gross
  Player tabs: A=Category, B=Movie, C=$$$
"""

import re, sys, csv, ssl, io, urllib.request, urllib.error, urllib.parse
from datetime import datetime

INDEX_FILE = "index.html"
SHEET_ID   = "1OtukeYm-dOOIbti3dujLxFTSEbQsyY_TSMmOeL8e-c4"
PUB_ID     = "2PACX-1vTJHbBU2trW4bFtUQ93Y0jhSB8W2uxegQxonwqKer-vUUsgFbpPfsYtnPcST5vJeiQA_mRkBNMBaZU7"

PLAYER_TABS = [
    "Pablo","Reuel","Josh","Dom","Tracy","Aarya","Megan",
    "AJ","Cecily","Daniel","Katie","Micah","Tizzle","Andrew"
]

# Column indices (0-based)
MOJO_TITLE_COL = 1   # B
MOJO_GROSS_COL = 5   # F (weekly gross — what we use, not cumulative)
PLAYER_MOVIE_COL = 1  # B
PLAYER_GROSS_COL = 2  # C

def make_ctx():
    return ssl.create_default_context()

def fetch_csv(sheet_name):
    name_enc = urllib.parse.quote(sheet_name)
    urls = [
        f"https://docs.google.com/spreadsheets/d/e/{PUB_ID}/pub?output=csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/pub?output=csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={name_enc}",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20, context=make_ctx()) as resp:
                text = resp.read().decode("utf-8-sig", errors="replace")
                if text.strip():
                    return text
        except Exception as e:
            print(f"    try failed: {e}")
    raise Exception(f"All URLs failed for '{sheet_name}'")

def parse_gross(val):
    """Convert '$403,288,805' or '403288805' to int. Returns None if N/A or blank."""
    if not val: return None
    v = str(val).strip().replace("$","").replace(",","").replace(" ","")
    if v.upper() in ("#N/A","N/A","#VALUE!","#REF!","#ERROR!","","NULL","FALSE","TRUE"):
        return None
    try:
        f = float(v)
        return int(f) if f > 100 else None
    except ValueError:
        return None

def fetch_all_grosses():
    all_grosses = {}

    # ── 2026_Mojo: use column F (index 5) = weekly/current gross ─────────────
    print("\n[SHEET] 2026_Mojo (col B=title, col F=gross)")
    try:
        text = fetch_csv("2026_Mojo")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        print(f"    {len(rows)} rows")
        found = 0
        for row in rows[1:]:  # skip header row 1
            if len(row) <= MOJO_TITLE_COL: continue
            title = str(row[MOJO_TITLE_COL]).strip()
            if not title or title.lower() in ("release","title","movie","b",""): continue
            gross = parse_gross(row[MOJO_GROSS_COL]) if len(row) > MOJO_GROSS_COL else None
            if title and gross:
                all_grosses[title.lower()] = gross
                found += 1
                print(f"    {title}: ${gross:,}")
        print(f"    {found} grosses extracted")
    except Exception as e:
        print(f"    WARN: {e}")

    # ── Player tabs: col B=movie, col C=$$$ ───────────────────────────────────
    for player in PLAYER_TABS:
        print(f"\n[SHEET] {player} (col B=movie, col C=gross)")
        try:
            text = fetch_csv(player)
            reader = csv.reader(io.StringIO(text))
            found = 0
            for row in reader:
                if len(row) <= PLAYER_MOVIE_COL: continue
                title = str(row[PLAYER_MOVIE_COL]).strip()
                # Skip header/total/blank rows
                if not title or title.lower() in (
                    "movie","title","total","b","","katie","pablo","daniel",
                    "dom","reuel","aarya","megan","aj","cecily","tracy",
                    "micah","tizzle","andrew","josh"
                ): continue
                gross = parse_gross(row[PLAYER_GROSS_COL]) if len(row) > PLAYER_GROSS_COL else None
                if gross:
                    # Player tabs are authoritative — override mojo value
                    all_grosses[title.lower()] = gross
                    found += 1
                    print(f"    {title}: ${gross:,}")
            print(f"    {found} grosses")
        except Exception as e:
            print(f"    WARN: {e}")

    return all_grosses

def patch_html(html, all_grosses):
    changes = 0

    def roster_replacer(m):
        nonlocal changes
        pre, old, suf = m.group(1), m.group(2), m.group(3)
        tm = re.search(r"movie:(?:'([^']+)'|\"([^\"]+)\")", pre)
        if not tm: return m.group(0)
        title = (tm.group(1) or tm.group(2)).lower()
        new = all_grosses.get(title)
        if new is None or str(new) == old: return m.group(0)
        changes += 1
        print(f"  roster  {title}: {old} -> {new}")
        return f"{pre}{new}{suf}"

    html = re.sub(
        r'(\{cat:[^}]+?movie:(?:\'[^\']+\'|"[^"]+"),gross:)(null|\d+)(\})',
        roster_replacer, html
    )

    def mojo_replacer(m):
        nonlocal changes
        pre, old, suf = m.group(1), m.group(2), m.group(3)
        tm = re.search(r"title:(?:'([^']+)'|\"([^\"]+)\")", pre)
        if not tm: return m.group(0)
        title = (tm.group(1) or tm.group(2)).lower()
        new = all_grosses.get(title)
        if new is None or str(new) == old: return m.group(0)
        changes += 1
        print(f"  mojo    {title}: ${int(old):,} -> ${new:,}")
        return f"{pre}{new}{suf}"

    html = re.sub(
        r'(\{rank:\d+,title:(?:\'[^\']+\'|"[^"]+"),gross:)(\d+)(\})',
        mojo_replacer, html
    )
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

def main():
    print(f"[{datetime.utcnow().isoformat()}] Updating from Google Sheet...")

    all_grosses = fetch_all_grosses()

    if not all_grosses:
        print("\n[ERROR] No data retrieved from any sheet tab.")
        print("Ensure sheet is published: File -> Share -> Publish to web -> Publish")
        sys.exit(1)

    print(f"\n[INFO] {len(all_grosses)} gross values fetched")

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    print("\n[INFO] Patching index.html...")
    html, changes = patch_html(html, all_grosses)
    html = add_timestamp(html)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[DONE] {changes} values updated")
    if changes == 0:
        print("[INFO] All values already match the sheet")

if __name__ == "__main__":
    main()
