#!/usr/bin/env python3
"""
update_grosses.py - DEBUG VERSION
Prints raw CSV data so we can see exactly what the sheet is returning.
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

def make_ctx():
    return ssl.create_default_context()

def fetch_csv(sheet_name):
    name_enc = urllib.parse.quote(sheet_name)
    urls = [
        f"https://docs.google.com/spreadsheets/d/e/{PUB_ID}/pub?output=csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/pub?output=csv&sheet={name_enc}",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={name_enc}",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20, context=make_ctx()) as resp:
                text = resp.read().decode("utf-8-sig", errors="replace")
                if text.strip():
                    print(f"    fetched from: {url[:80]}")
                    return text
        except Exception as e:
            print(f"    failed: {e}")
    raise Exception(f"All URLs failed for '{sheet_name}'")

def main():
    print(f"[{datetime.utcnow().isoformat()}] DEBUG: printing raw sheet data\n")

    # Print first 5 rows of 2026_Mojo
    print("=== 2026_Mojo RAW ROWS ===")
    try:
        text = fetch_csv("2026_Mojo")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        print(f"Total rows: {len(rows)}")
        for i, row in enumerate(rows[:8]):
            print(f"row[{i}]: {row}")
    except Exception as e:
        print(f"ERROR: {e}")

    # Print first 5 rows of Katie
    print("\n=== Katie RAW ROWS ===")
    try:
        text = fetch_csv("Katie")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        print(f"Total rows: {len(rows)}")
        for i, row in enumerate(rows[:12]):
            print(f"row[{i}]: {row}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
