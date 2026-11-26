"""Checks on the live data read by Commodity Radar (added 26 Nov 2026, for the data repair loop).

Run from the repository root:  python -I -m unittest discover -s tests -v
Each live/*.json file loads, has the expected shape, and no id has disappeared since the last commit (HEAD).
Read-only: nothing is written, committed or pushed."""
import json, re, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "live"
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"https?://\S+$")
REQUIRED = {
    "events": ["id", "date", "commodity", "place", "title", "source", "url"],
    "calendar": ["id", "date", "time", "region", "type", "event"],
    "rates": ["id", "bank", "date", "rate", "url"],
    "editions": ["id", "date", "stories"],
}
STORY = ["title", "lead", "sources"]


def load(name):
    return json.loads((LIVE / f"{name}.json").read_text(encoding="utf-8"))


def at_head(name):
    """The file as it was at the last commit, or None (new file, no git)."""
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:live/{name}.json"], capture_output=True)
    return json.loads(r.stdout.decode("utf-8")) if r.returncode == 0 else None


class ListFiles(unittest.TestCase):
    def test_shape(self):
        for name, keys in REQUIRED.items():
            with self.subTest(file=name):
                items = load(name)
                self.assertIsInstance(items, list)
                self.assertTrue(items, f"{name}.json is empty")
                ids = [x.get("id") for x in items]
                self.assertEqual(len(ids), len(set(ids)), f"{name}.json: duplicate ids")
                for x in items:
                    for k in keys:
                        self.assertIn(k, x, f"{name}.json, id {x.get('id')}: missing {k}")
                    self.assertRegex(x["date"], DATE, f"{name}.json, id {x['id']}: bad date")
                    if x.get("url"):
                        self.assertRegex(x["url"], URL, f"{name}.json, id {x['id']}: bad url")

    def test_editions_stories(self):
        for e in load("editions"):
            self.assertIsInstance(e["stories"], list)
            self.assertTrue(e["stories"], f"edition {e['id']} has no story")
            for s in e["stories"]:
                for k in STORY:
                    self.assertIn(k, s, f"edition {e['id']}: a story misses {k}")
                self.assertTrue(s["sources"], f"edition {e['id']}: story without a source ({s.get('title')})")

    def test_rates_are_numbers(self):
        for r in load("rates"):
            self.assertIsInstance(r["rate"], (int, float), f"rate {r['id']} is not a number")

    def test_no_id_disappeared(self):
        for name in REQUIRED:
            with self.subTest(file=name):
                old = at_head(name)
                if old is None:
                    self.skipTest("no committed version")
                gone = {x["id"] for x in old} - {x["id"] for x in load(name)}
                self.assertFalse(gone, f"{name}.json: ids gone since the last commit: {sorted(gone)[:10]}")


class Market(unittest.TestCase):
    def test_shape(self):
        m = load("market")
        for k in ("source", "licence", "url", "updated", "months", "series"):
            self.assertIn(k, m)
        months = m["months"]
        self.assertGreaterEqual(len(months), 24)
        for a, b in zip(months, months[1:]):
            ya, ma = map(int, a.split("-")); yb, mb = map(int, b.split("-"))
            self.assertEqual((yb * 12 + mb) - (ya * 12 + ma), 1, f"months not consecutive: {a} then {b}")
        for key, s in m["series"].items():
            self.assertEqual(len(s["v"]), len(months), f"series {key}: {len(s['v'])} values for {len(months)} months")
            self.assertGreater(sum(v is not None for v in s["v"]), len(months) // 2, f"series {key}: too many gaps")

    def test_no_series_disappeared(self):
        old = at_head("market")
        if old is None:
            self.skipTest("no committed version")
        gone = set(old["series"]) - set(load("market")["series"])
        self.assertFalse(gone, f"market.json: series gone since the last commit: {sorted(gone)}")


if __name__ == "__main__":
    unittest.main()
