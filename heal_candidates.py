import json, time, subprocess
from pathlib import Path
import tvlib

OUT = Path("docs/heal_candidates_report.txt")
CACHE = Path("candidate_health.json")
DB_FILE = Path("channel_database.json")
MAX_PER_CHANNEL = 10
TIMEOUT = 5

def test_url(url):
    start = time.time()
    try:
        r = subprocess.run(
            ["curl", "-L", "--max-time", str(TIMEOUT), url],
            capture_output=True,
            text=True
        )
        elapsed = round(time.time() - start, 3)
        text = (r.stdout + r.stderr).lower()
        ok = "#extm3u" in text or "#ext-x-" in text or "content-type" in text
        return ok, elapsed
    except Exception:
        return False, round(time.time() - start, 3)

whitelist = json.load(open("channel_whitelist.json"))
channels = tvlib.load_all_sources()
cache = json.load(open(CACHE)) if CACHE.exists() else {}
db = json.load(open(DB_FILE)) if DB_FILE.exists() else {}

report = []
now = int(time.time())

for group, wanted_list in whitelist["categories"].items():
    for wanted in wanted_list:
        entry = db.setdefault(wanted, {"group": group, "name": wanted, "candidates": {}})
        entry["group"] = group
        entry["name"] = wanted

        candidates = [
            ch for ch in channels
            if tvlib.match_channel(ch, wanted, whitelist)
            and not tvlib.is_rejected(ch, wanted, whitelist)
        ]

        tested = []
        for ch in candidates[:MAX_PER_CHANNEL]:
            url = ch["url"]
            ok, seconds = test_url(url)

            cache[url] = {
                "ok": ok,
                "seconds": seconds,
                "channel": wanted,
                "raw": ch["name"],
                "source": ch["source"],
                "checked": now
            }

            c = entry["candidates"].setdefault(url, {})
            c.update({
                "url": url,
                "source": ch["source"],
                "raw": ch["name"],
                "info": ch["info"],
                "last_checked": now,
                "last_seconds": seconds,
                "last_status": ok,
            })

            c["checks"] = c.get("checks", 0) + 1
            if ok:
                c["successes"] = c.get("successes", 0) + 1
                c["last_ok"] = now
            else:
                c["failures"] = c.get("failures", 0) + 1

            tested.append((ok, seconds, ch))

        tested.sort(key=lambda x: (not x[0], x[1]))

        report.append(f"\n=== {wanted} [{group}] ===")
        if not tested:
            report.append("NO CANDIDATES")
        else:
            for ok, seconds, ch in tested[:5]:
                report.append(f"{'OK ' if ok else 'BAD'} {seconds:5}s | {ch['source']} | {ch['name']} | {ch['url']}")

CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
DB_FILE.write_text(json.dumps(db, indent=2), encoding="utf-8")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(report) + "\n", encoding="utf-8")

print(f"Wrote {OUT}")
print(f"Wrote {CACHE}")
print(f"Updated {DB_FILE}")
