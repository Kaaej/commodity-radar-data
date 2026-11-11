"""Merge the morning market watch into live/*.json, publish it, and check it online.

Usage: python add_live.py <incoming.json> [--dry-run] [--no-verify]
incoming.json holds any of these lists, each item with an "id" (same doc_id as in the
Claude artifact database):
  {"events": [...], "rates": [...], "calendar": [...], "editions": [...]}

Write rules (nothing is ever deleted or silently overwritten):
  events, editions: a new id is added; an existing id is left as it is (reported).
  calendar: a new id is added; on an existing id, only empty or missing fields are
            filled (typically "actual"); a field that already has a value is kept.
  rates:    a new id is added; an existing id is replaced only by a decision with
            the same or a later date (it holds the latest decision per country).
Checks before commit: the JSON files are valid lists, no id has disappeared, no file
has fewer items than before, every incoming item is present. If a check fails,
nothing is written, committed or pushed.
Check after push: GitHub serves every incoming id (raw.githubusercontent.com, read by the site) within 3 minutes.
The last line printed starts with OK or FAILED, for the morning task's report.
"""
import json, subprocess, sys, time, datetime, urllib.request
from pathlib import Path

SITE = "https://raw.githubusercontent.com/Kaaej/commodity-radar-data/main/live/"
NAMES = ("events", "rates", "calendar", "editions")
SORT = {"events": "date", "calendar": "date", "editions": "date", "rates": "id"}
root = Path(__file__).parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
dry, no_verify = "--dry-run" in sys.argv, "--no-verify" in sys.argv


def fail(msg):
    print("FAILED:", msg)
    sys.exit(1)


try:
    inc = json.loads(Path(args[0]).read_text(encoding="utf-8"))
except Exception as e:
    fail(f"cannot read the incoming file ({e})")

before, after, report, expected = {}, {}, [], {}
for name in NAMES:
    path = root / "live" / f"{name}.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not isinstance(rows, list):
        fail(f"live/{name}.json is not a list")
    before[name] = {r["id"]: r for r in rows}
    cur = {k: dict(v) for k, v in before[name].items()}
    added = updated = kept = 0
    for item in inc.get(name) or []:
        if not isinstance(item, dict) or not item.get("id"):
            fail(f"an item in {name} has no id")
        i = item["id"]
        expected.setdefault(name, set()).add(i)
        if i not in cur:
            cur[i] = item
            added += 1
        elif name in ("events", "editions"):
            kept += 1
        elif name == "calendar":
            filled = {k: v for k, v in item.items() if k != "id" and v not in (None, "") and cur[i].get(k) in (None, "")}
            if filled:
                cur[i].update(filled)
                updated += 1
            else:
                kept += 1
        elif name == "rates":
            if str(item.get("date", "")) >= str(cur[i].get("date", "")):
                cur[i] = item
                updated += 1
            else:
                kept += 1
    after[name] = cur
    if added or updated or kept:
        report.append(f"{name} +{added} updated {updated} kept {kept}")

# safety checks before anything is written
for name in NAMES:
    lost = set(before[name]) - set(after[name])
    if lost:
        fail(f"{name}: ids would disappear: {sorted(lost)}")
    if len(after[name]) < len(before[name]):
        fail(f"{name}: fewer items than before")
    missing = expected.get(name, set()) - set(after[name])
    if missing:
        fail(f"{name}: incoming ids missing after merge: {sorted(missing)}")

changed = [n for n in NAMES if after[n] != before[n]]
if not changed:
    print("OK: nothing new to publish (" + ("; ".join(report) or "empty incoming file") + ")")
    sys.exit(0)
if dry:
    print("OK (dry run, nothing written): " + "; ".join(report))
    sys.exit(0)

for name in changed:
    rows = sorted(after[name].values(), key=lambda r: str(r.get(SORT[name], "")), reverse=(name != "rates"))
    (root / "live" / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

day = datetime.date.today().isoformat()
msg = f"Market watch {day}: " + "; ".join(report)
try:
    subprocess.run(["git", "-C", str(root), "add", "live"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", msg], check=True)
    # Since 11 Nov 2026 a GitHub Action also commits live/market.json: take its commits first (no shared files, so no conflict)
    subprocess.run(["git", "-C", str(root), "pull", "--rebase", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "push", "-q"], check=True)
except subprocess.CalledProcessError as e:
    fail(f"git step failed ({e}); the files are written locally but not online")

if no_verify:
    print("OK (pushed, not checked online): " + msg)
    sys.exit(0)

# check the live site
deadline = time.time() + 180
while True:
    missing = []
    for name, ids in expected.items():
        try:
            req = urllib.request.Request(SITE + f"{name}.json?t={int(time.time())}", headers={"Cache-Control": "no-cache"})
            online = {r["id"] for r in json.load(urllib.request.urlopen(req, timeout=20))}
        except Exception:
            online = set()
        missing += [f"{name}/{i}" for i in ids - online]
    if not missing:
        print("OK: published and checked online: " + msg)
        sys.exit(0)
    if time.time() > deadline:
        fail("pushed to GitHub but not yet served by raw.githubusercontent.com after 3 minutes: " + ", ".join(missing[:10]))
    time.sleep(15)
