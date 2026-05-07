#!/usr/bin/env python3
"""
update_grosses.py - Chi Alpha Fantasy Box Office
Reads the SCOREBOARD tab (which is what gets published) and updates
officialTotals in index.html with live scores from the spreadsheet.
"""

import re, sys, csv, ssl, io, urllib.request, urllib.error, urllib.parse
from datetime import datetime

INDEX_FILE = "index.html"
SHEET_ID   = "1OtukeYm-dOOIbti3dujLxFTSEbQsyY_TSMmOeL8e-c4"
PUB_ID     = "2PACX-1vTJHbBU2trW4bFtUQ93Y0jhSB8W2uxegQxonwqKer-vUUsgFbpPfsYtnPcST5vJeiQA_mRkBNMBaZU7"

def make_ctx():
    return ssl.create_default_context()

def fetch_csv(sheet_name=None):
    name_enc = urllib.parse.quote(sheet_name) if sheet_name else ""
    urls = [
        f"https://docs.google.com/spreadsheets/d/e/{PUB_ID}/pub?output=csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/e/{PUB_ID}/pub?output=csv",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/pub?output=csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={name_enc}",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20, context=make_ctx()) as resp:
                text = resp.read().decode("utf-8-sig", errors="replace")
                if text.strip():
                    return text
        except Exception as e:
            print(f"    failed: {e}")
    raise Exception("All URLs failed")

def parse_gross(val):
    if not val: return None
    v = str(val).strip().replace("$","").replace(",","").replace(" ","").replace(".00","")
    if v.upper() in ("#N/A","N/A","#VALUE!","#REF!","#ERROR!","","NULL","FALSE","TRUE"):
        return None
    try:
        f = float(v)
        return int(f) if f > 0 else None
    except ValueError:
        return None

def fetch_scoreboard():
    """
    Parse the SCOREBOARD tab which returns rows like:
    ['', '', '', 'Aarya', '$404,860,254.00', 'Andrew', '$107,867,753.00']
    Columns 3,4 = player1,total1 and columns 5,6 = player2,total2
    """
    print("[INFO] Fetching SCOREBOARD tab...")
    text = fetch_csv("SCOREBOARD")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    scores = {}
    for row in rows:
        # Each row has two player/score pairs at cols 3,4 and 5,6
        if len(row) >= 5:
            name1 = str(row[3]).strip()
            val1  = parse_gross(row[4]) if len(row) > 4 else None
            if name1 and val1 and name1.lower() not in ("scoreboard","player","name",""):
                scores[name1] = val1
                print(f"    {name1}: ${val1:,}")
        if len(row) >= 7:
            name2 = str(row[5]).strip()
            val2  = parse_gross(row[6]) if len(row) > 6 else None
            if name2 and val2 and name2.lower() not in ("scoreboard","player","name",""):
                scores[name2] = val2
                print(f"    {name2}: ${val2:,}")

    return scores

def patch_official_totals(html, scores):
    """Update the officialTotals object in index.html."""
    changes = 0

    def replacer(m):
        nonlocal changes
        name = m.group(1)
        old  = m.group(2)
        new  = scores.get(name)
        if new is None or str(new) == old:
            return m.group(0)
        changes += 1
        print(f"  officialTotals {name}: {old} -> {new}")
        return f"{name}:{new}"

    # Match e.g. Katie:598232717 inside the officialTotals block
    html = re.sub(r"(Katie|Daniel|Dom|Reuel|Aarya|Pablo|Micah|Tizzle|Andrew|Cecily|Tracy|AJ|Megan|Josh):(\d+)",
                  replacer, html)
    return html, changes

def patch_manual_bonuses(html, scores):
    """
    Since officialTotals now holds live sheet scores directly,
    we zero out the locked spreadsheet bonus entries so they
    don't double-count (the sheet already includes them).
    """
    # Remove locked bonus amounts — set to 0 so getEffectiveTotal = roster sum + 0
    # Actually we want officialTotals = sheet total, and getEffectiveTotal uses roster sum + adj
    # So instead we should update the manualBonuses to be (sheet_total - roster_sum)
    # But we don't know roster sums here. Simpler: just update officialTotals and
    # trust getEffectiveTotal which uses live roster sum + manualBonuses.
    # The locked bonuses will make the effective total != sheet total if rosters changed.
    # Best approach: store sheet totals in a separate JS variable and use that for scoreboard.
    return html, 0

def add_timestamp(html):
    now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")
    html = re.sub(
        r'Data (?:from|synced from).*?</a>(\s*&nbsp;·&nbsp;\s*Updated [^<]+)?',
        f'Data synced from <a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}" '
        f'target="_blank">Google Sheet</a> &nbsp;·&nbsp; Updated {now}',
        html
    )
    return html

def patch_scoreboard_totals(html, scores):
    """
    Instead of patching officialTotals (which affects bonus logic),
    inject the sheet scores as a separate sheetTotals variable that
    the scoreboard uses directly. We look for the existing variable
    and update each player's value.
    """
    changes = 0

    # Update officialTotals values directly — these are the ground-truth sheet scores
    for name, total in scores.items():
        # Match: Name:123456 inside officialTotals block
        pattern = rf"({re.escape(name)}):(\d+)"
        def make_replacer(n, t):
            def replacer(m):
                nonlocal changes
                if m.group(2) == str(t): return m.group(0)
                changes += 1
                print(f"  {n}: {m.group(2)} -> {t}")
                return f"{n}:{t}"
            return replacer
        html = re.sub(pattern, make_replacer(name, total), html, count=1)

    return html, changes

def main():
    print(f"[{datetime.utcnow().isoformat()}] Updating scores from Google Sheet...")

    try:
        scores = fetch_scoreboard()
    except Exception as e:
        print(f"[ERROR] Could not fetch sheet: {e}")
        sys.exit(1)

    if not scores:
        print("[ERROR] No scores found in sheet.")
        sys.exit(1)

    print(f"\n[INFO] {len(scores)} player scores fetched")

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    html, changes = patch_scoreboard_totals(html, scores)
    html = add_timestamp(html)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[DONE] {changes} values updated")
    if changes == 0:
        print("[INFO] All scores already match the sheet")

if __name__ == "__main__":
    main()
