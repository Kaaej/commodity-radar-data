"""Monthly commodity prices for Commodity Radar (Market section).

Source: World Bank Commodity Price Data (The Pink Sheet), monthly averages in nominal US dollars,
licence CC BY 4.0. The World Bank publishes a new file early each month, at an address that changes;
this script finds the current link on the Commodity Markets page, keeps the last 61 months of the
series the site uses and writes live/market.json.

Usage:
  python market.py            write live/market.json if the data changed (no git)
  python market.py --push     same, then commit and push to GitHub when the file changed
Added 11 Nov 2026.
"""
import io, json, re, subprocess, sys, urllib.request
from pathlib import Path

import openpyxl

ROOT = Path(__file__).parent
OUT = ROOT / "live" / "market.json"
PAGE = "https://www.worldbank.org/en/research/commodity-markets"
UA = {"User-Agent": "Mozilla/5.0 (commodity-radar data script)"}
MONTHS = 61  # five years and the month before, for year-on-year changes

# site key -> exact column title in the "Monthly Prices" sheet
SERIES = {
    "brent": "Crude oil, Brent", "dubai": "Crude oil, Dubai", "wti": "Crude oil, WTI",
    "coal_au": "Coal, Australian", "coal_za": "Coal, South African **",
    "gas_us": "Natural gas, US", "gas_eu": "Natural gas, Europe", "lng_jp": "Liquefied natural gas, Japan",
    "coffee_ara": "Coffee, Arabica", "coffee_rob": "Coffee, Robusta", "palm": "Palm oil",
    "soy": "Soybeans", "soy_oil": "Soybean oil", "soy_meal": "Soybean meal", "maize": "Maize",
    "wheat_srw": "Wheat, US SRW", "wheat_hrw": "Wheat, US HRW",
    "logs_my": "Logs, Malaysian", "sawn_my": "Sawnwood, Malaysian",
    "alu": "Aluminum", "ironore": "Iron ore, cfr spot", "copper": "Copper", "nickel": "Nickel",
    "gold": "Gold", "silver": "Silver",
}


def fail(msg):
    print("FAILED " + msg)
    sys.exit(1)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def main():
    push = "--push" in sys.argv
    try:
        html = get(PAGE).decode("utf-8", "replace")
    except Exception as e:
        fail(f"World Bank page not reachable ({e})")
    m = re.search(r'https://thedocs\.worldbank\.org/[^"\']*CMO-Historical-Data-Monthly\.xlsx', html)
    if not m:
        fail("link to CMO-Historical-Data-Monthly.xlsx not found on the World Bank page")
    url = m.group(0)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(get(url)), read_only=True, data_only=True)
        rows = list(wb["Monthly Prices"].iter_rows(values_only=True))
    except Exception as e:
        fail(f"Pink Sheet file unreadable ({e})")
    updated = str(rows[3][0] or "").replace("Updated on", "").strip()
    titles = [str(h).strip() if h else "" for h in rows[4]]
    units = [str(u).strip("() ") if u else "" for u in rows[5]]
    data = [r for r in rows[6:] if r and isinstance(r[0], str) and re.fullmatch(r"\d{4}M\d{2}", r[0])]
    data = data[-MONTHS:]
    months = [f"{r[0][:4]}-{r[0][5:]}" for r in data]
    out = {"source": "World Bank Commodity Price Data (The Pink Sheet), monthly averages, nominal US dollars",
           "licence": "CC BY 4.0", "url": PAGE, "updated": updated, "months": months, "series": {}}
    for key, title in SERIES.items():
        if title not in titles:
            fail(f"column not found: {title}")
        j = titles.index(title)
        vals = [r[j] if isinstance(r[j], (int, float)) else None for r in data]
        if sum(v is not None for v in vals) < MONTHS // 2:
            fail(f"too few values for {title}")
        out["series"][key] = {"name": title.replace(" **", ""), "unit": units[j], "v": [None if v is None else round(v, 4) for v in vals]}
    new = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if new == old:
        print(f"OK unchanged (last month {months[-1]}, World Bank update {updated})")
        return
    OUT.write_text(new, encoding="utf-8")
    if not push:
        print(f"OK written, not pushed (last month {months[-1]}, World Bank update {updated})")
        return
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "live/market.json"], check=True)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m", f"Market prices to {months[-1]} (World Bank, {updated})"], check=True)
        # Since 11 Nov 2026 a GitHub Action also commits live/market.json: take its commits first (no shared files, so no conflict)
        subprocess.run(["git", "-C", str(ROOT), "pull", "--rebase", "-q"], check=True)
        subprocess.run(["git", "-C", str(ROOT), "push", "-q"], check=True)
    except subprocess.CalledProcessError as e:
        fail(f"git step failed ({e}); live/market.json is written locally but not online")
    print(f"OK pushed (last month {months[-1]}, World Bank update {updated})")


if __name__ == "__main__":
    main()
