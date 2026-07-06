import json, time, subprocess
from pathlib import Path
import build_playlist

OUT = Path("docs/candidate_health_report.txt")
CACHE = Path("candidate_health.json")
MAX_CANDIDATES = 8
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
channels = build_playlist.load_sources()
cache = json.load(open(CACHE)) if CACHE.exists() else {}
report = []

for group, names in db["categories"].items():
    for wanted in names:
        candidates = [
            ch for ch in channels
            if build_playlist.match_channel(ch, wanted, db)
            and not build_playlist.is_rejected(ch, wanted, db)
        ]

        report.append(f"\n=== {wanted} [{group}] ===")
        if not candidates:
            report.append("NO CANDIDATES")
            continue

        tested = []
        for ch in candidates[:MAX_CANDIDATES]:
            url = ch["url"]
            if url in cache:
                ok = cache[url]["ok"]
                seconds = cache[url]["seconds"]
            else:
                ok, seconds = test_url(url)
                cache[url] = {
                    "ok": ok,
                    "seconds": seconds,
                    "channel": wanted,
                    "raw": ch["name"],
                    "source": ch["source"],
                    "checked": int(time.time())
                }
            tested.append((ok, seconds, ch))

        tested.sort(key=lambda x: (not x[0], x[1]))

        for ok, seconds, ch in tested[:10]:
            report.append(f"{'OK ' if ok else 'BAD'} {seconds:5}s | {ch['source']} | {ch['name']} | {ch['url']}")

CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(report) + "\n", encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Wrote {CACHE}")
