#!/usr/bin/env python3
"""
update_grosses.py
Pulls box office grosses from the published Chi Alpha Fantasy Google Sheet
and patches index.html. No API key required.
"""

import re, sys, csv, ssl, io, urllib.request, urllib.error, urllib.parse
from datetime import datetime

INDEX_FILE = "index.html"
SHEET_ID   = "1OtukeYm-dOOIbti3dujLxFTSEbQsyY_TSMmOeL8e-c4"   # edit ID
PUB_ID     = "2PACX-1vTJHbBU2trW4bFtUQ93Y0jhSB8W2uxegQxonwqKer-vUUsgFbpPfsYtnPcST5vJeiQA_mRkBNMBaZU7"  # published ID

PLAYER_TABS = [
    "Pablo","Reuel","Josh","Dom","Tracy","Aarya","Megan",
    "AJ","Cecily","Daniel","Katie","Micah","Tizzle","Andrew"
]

def make_ctx():
    return ssl.create_default_context()

def fetch_csv(sheet_name):
    """Try multiple URL formats — published ID first, then edit ID fallbacks."""
    name_enc = urllib.parse.quote(sheet_name)
    urls = [
        # Published ID (most reliable after publishing to web)
        f"https://docs.google.com/spreadsheets/d/e/{PUB_ID}/pub?output=csv&sheet={name_enc}",
        # Edit ID with pub endpoint
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/pub?output=csv&sheet={name_enc}",
        # gviz endpoint
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={name_enc}",
        # Direct export
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={name_enc}",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; chi-alpha-bot/1.0)"
            })
            with urllib.request.urlopen(req, timeout=20, context=make_ctx()) as resp:
                text = resp.read().decode("utf-8-sig", errors="replace")
                if text.strip():
                    print(f"    OK: {url[:80]}")
                    return text
        except urllib.error.HTTPError as e:
            body = e.read(200).decode("utf-8", errors="replace")
            print(f"    HTTP {e.code} ({url[:60]}): {body[:60]}")
        except Exception as e:
            print(f"    ERR ({url[:60]}): {e}")
    raise Exception(f"All URLs failed for sheet tab '{sheet_name}'")

def parse_gross(val):
    if not val: return None
    v = str(val).strip().replace("$","").replace(",","").replace(" ","")
    if v.upper() in ("#N/A","N/A","#VALUE!","#REF!","#ERROR!","","NULL","NONE","FALSE","TRUE"):
        return None
    try:
        f = float(v)
        return int(f) if f > 100 else None
    except ValueError:
        return None

def fetch_all_grosses():
    all_grosses = {}

    # 2026_Mojo tab
    print("\n[SHEET] 2026_Mojo")
    try:
        text = fetch_csv("2026_Mojo")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        print(f"    {len(rows)} rows")
        for row in rows[1:]:
            if len(row) < 2: continue
            title = row[1].strip()
            if not title or title.lower() in ("release","title","movie",""): continue
            gross = None
            for col in [7, 5, 6, 4]:
                if len(row) > col:
                    gross = parse_gross(row[col])
                    if gross: break
            if title and gross:
                all_grosses[title.lower()] = gross
                print(f"    {title}: ${gross:,}")
    except Exception as e:
        print(f"    WARN: {e}")

    # Player tabs
    for player in PLAYER_TABS:
        print(f"\n[SHEET] {player}")
        try:
            text = fetch_csv(player)
            reader = csv.reader(io.StringIO(text))
            found = 0
            for row in reader:
                if len(row) < 3: continue
                title = row[1].strip()
                if not title or title.lower() in ("movie","title","total",""): continue
                gross = parse_gross(row[2])
                if gross:
                    all_grosses[title.lower()] = gross
                    found += 1
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
        print("Make sure the sheet is published: File -> Share -> Publish to web -> Publish")
        sys.exit(1)

    print(f"\n[INFO] {len(all_grosses)} gross values fetched")

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    html, changes = patch_html(html, all_grosses)
    html = add_timestamp(html)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[DONE] {changes} values updated")

if __name__ == "__main__":
    main()
