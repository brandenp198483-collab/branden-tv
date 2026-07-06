import json, time, subprocess
from pathlib import Path
import tvlib

OUT = Path("docs/heal_candidates_report.txt")
CACHE = Path("candidate_health.json")
MAX_PER_CHANNEL = 10
TIMEOUT = 5

def test_url(url):
    start = time.time()
    try:
        r = subprocess.run(
            ["curl", "-L", "--max-time", str(TIMEOUT), "-I", url],
            capture_output=True,
            text=True
        )
        elapsed = round(time.time() - start, 3)
        text = (r.stdout + r.stderr).lower()
        ok = any(x in text for x in ["200 ok", "content-type", "mpegurl", "application/vnd.apple.mpegurl"])
        return ok, elapsed
    except Exception:
        return False, round(time.time() - start, 3)

db = json.load(open("channel_whitelist.json"))
channels = tvlib.load_all_sources()
cache = json.load(open(CACHE)) if CACHE.exists() else {}
report = []

for group, wanted_list in db["categories"].items():
    for wanted in wanted_list:
        candidates = [
            ch for ch in channels
            if tvlib.match_channel(ch, wanted, db)
            and not tvlib.is_rejected(ch, wanted, db)
        ]

        tested = []
        for ch in candidates[:MAX_PER_CHANNEL]:
            url = ch["url"]
            if url not in cache:
                ok, seconds = test_url(url)
                cache[url] = {
                    "ok": ok,
                    "seconds": seconds,
                    "channel": wanted,
                    "raw": ch["name"],
                    "source": ch["source"],
                    "checked": int(time.time())
                }
            else:
                ok = cache[url]["ok"]
                seconds = cache[url]["seconds"]

            tested.append((ok, seconds, ch))

        tested.sort(key=lambda x: (not x[0], x[1]))

        report.append(f"\n=== {wanted} [{group}] ===")
        if not tested:
            report.append("NO CANDIDATES")
        else:
            for ok, seconds, ch in tested[:5]:
                report.append(f"{'OK ' if ok else 'BAD'} {seconds:5}s | {ch['source']} | {ch['name']} | {ch['url']}")

CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(report) + "\n", encoding="utf-8")

print(f"Wrote {OUT}")
print(f"Wrote {CACHE}")
