import json, time, subprocess
from pathlib import Path

PLAYLIST = Path("docs/BrandenTV-Stremio.m3u")
OUT = Path("stream_health.json")

def parse_m3u(path):
    lines = path.read_text(errors="ignore").splitlines()
    info = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif info and line.startswith("http"):
            name = info.split(",")[-1].strip()
            yield name, line
            info = None

results = {}

for name, url in parse_m3u(PLAYLIST):
    print(f"Testing {name}...")
    start = time.time()
    ok = False
    err = ""

    try:
        r = subprocess.run(
            ["curl", "-L", "--max-time", "8", "-I", url],
            capture_output=True,
            text=True
        )
        elapsed = round(time.time() - start, 3)
        text = (r.stdout + r.stderr).lower()

        if "200 ok" in text or "content-type" in text or "mpegurl" in text:
            ok = True
        else:
            err = text[-200:]

    except Exception as e:
        elapsed = round(time.time() - start, 3)
        err = str(e)

    results[url] = {
        "channel": name,
        "ok": ok,
        "seconds": elapsed,
        "checked": int(time.time()),
        "error": err
    }

    print(f"  {'OK' if ok else 'BAD'} {elapsed}s")

OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

good = sum(1 for x in results.values() if x["ok"])
bad = len(results) - good

print()
print(f"Checked: {len(results)}")
print(f"Good: {good}")
print(f"Bad: {bad}")
print(f"Wrote: {OUT}")
