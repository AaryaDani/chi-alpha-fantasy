#!/usr/bin/env python3
"""
update_grosses.py
Fetches 2026 box office data from The Numbers and patches index.html
with updated grosses for every movie in the rosters and mojoData array.
"""

import re
import sys
import time
import json
import urllib.request
import urllib.error
from datetime import datetime

NUMBERS_URL = "https://www.the-numbers.com/market/2026/top-grossing-movies"
INDEX_FILE  = "index.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Titles that differ between our roster names and The Numbers ──────────────
# Key = our title (lowercase), Value = what The Numbers calls it (lowercase)
ALIAS = {
    "the super mario galaxy movie":     "super mario galaxy movie",
    "lee cronin's the mummy":           "mummy",
    "ready or not 2: here i come":      "ready or not 2",
    "ready or not 2":                   "ready or not 2",
    "insidious: out of the further":    "insidious",
    "the devil wears prada 2":          "devil wears prada",
    "the strangers: chapter 3":         "strangers: chapter 3",
    "the pout-pout fish":               "pout-pout fish",
    "i can only imagine 2":             "i can only imagine",
}


def fetch_numbers():
    """Return {title_lower: gross_int} from The Numbers 2026 chart."""
    req = urllib.request.Request(NUMBERS_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"[ERROR] Could not fetch The Numbers: {e}")
        sys.exit(1)

    # Each row looks like:
    # <td ...>1</td><td ...><a href="...">Title</a></td>...<td ...>$123,456,789</td>
    rows = re.findall(
        r'<tr[^>]*>.*?<td[^>]*>\d+</td>.*?<a[^>]*>([^<]+)</a>.*?'
        r'\$([0-9,]+).*?</tr>',
        html, re.DOTALL
    )

    grosses = {}
    for title, gross_str in rows:
        title_clean = title.strip()
        gross_int   = int(gross_str.replace(",", ""))
        grosses[title_clean.lower()] = (gross_int, title_clean)

    print(f"[INFO] Fetched {len(grosses)} titles from The Numbers")
    return grosses


def lookup(grosses, our_title):
    """Try to find our_title in the grosses dict, using aliases as fallback."""
    tl = our_title.lower()

    # Direct match
    if tl in grosses:
        return grosses[tl][0]

    # Alias match
    alias = ALIAS.get(tl)
    if alias and alias in grosses:
        return grosses[alias][0]

    # Partial match (our title is a substring of a Numbers title or vice-versa)
    for numbers_title, (gross, _) in grosses.items():
        if tl in numbers_title or numbers_title in tl:
            return gross

    return None


def patch_mojodata(html, grosses):
    """Update the mojoData array in index.html with fresh grosses."""
    changes = 0

    def replacer(m):
        nonlocal changes
        title     = m.group(1).strip("'\"")
        old_gross = int(m.group(2))
        new_gross = lookup(grosses, title)

        if new_gross is None or new_gross == old_gross:
            return m.group(0)

        changes += 1
        print(f"  mojoData  {title}: ${old_gross:,} → ${new_gross:,}")
        return m.group(0).replace(f"gross:{old_gross}", f"gross:{new_gross}")

    html = re.sub(
        r'\{rank:\d+,title:([\'"][^\'"]+[\'"]),'
        r'gross:(\d+)\}',
        replacer,
        html
    )
    return html, changes


def patch_rosters(html, grosses):
    """Update gross values inside the rosters object."""
    changes = 0

    def replacer(m):
        nonlocal changes
        movie     = m.group(1).strip("'\"")
        old_gross = m.group(2)

        new_gross = lookup(grosses, movie)
        if new_gross is None:
            return m.group(0)

        old_int = int(old_gross) if old_gross != "null" else None
        if old_int == new_gross:
            return m.group(0)

        changes += 1
        print(f"  roster    {movie}: {old_gross} → {new_gross}")
        return m.group(0).replace(f"gross:{old_gross}", f"gross:{new_gross}")

    # Match: movie:'Title',gross:12345  OR  movie:'Title',gross:null
    html = re.sub(
        r'\{cat:[^,]+,movie:([\'"][^\'"]+[\'"]),'
        r'gross:(null|\d+)\}',
        replacer,
        html
    )
    return html, changes


def patch_official_totals(html, grosses_map):
    """Recalculate officialTotals from live roster data after patching."""
    # We don't touch officialTotals here — getEffectiveTotal() reads live
    # roster sums at runtime, so updating the roster grosses is sufficient.
    return html


def add_updated_timestamp(html):
    """Update the footer timestamp."""
    now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")
    html = re.sub(
        r'Data from.*?The Numbers.*?</a>',
        f'Data from <a href="https://www.the-numbers.com/market/2026/top-grossing-movies" '
        f'target="_blank">The Numbers</a> &nbsp;·&nbsp; Updated {now}',
        html
    )
    return html


def main():
    print(f"[{datetime.utcnow().isoformat()}] Starting gross update...")

    grosses = fetch_numbers()

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    html, mojo_changes   = patch_mojodata(html, grosses)
    html, roster_changes = patch_rosters(html, grosses)
    html = add_updated_timestamp(html)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    total = mojo_changes + roster_changes
    print(f"[DONE] {total} values updated ({mojo_changes} mojoData, {roster_changes} roster entries)")
    if total == 0:
        print("[INFO] No changes — all grosses are already up to date")


if __name__ == "__main__":
    main()
