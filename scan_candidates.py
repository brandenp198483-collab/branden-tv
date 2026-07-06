import sys, re, time, subprocess
from pathlib import Path

FULL = Path("output/BrandenTV-Full.m3u")

def clean(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def parse_m3u(path):
    lines = path.read_text(errors="ignore").splitlines()
    info = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif info and line.startswith("http"):
            name = info.split(",")[-1].strip()
            yield name, info, line
            info = None

def test_url(url):
    start = time.time()
    try:
        r = subprocess.run(
            ["curl", "-L", "--max-time", "8", "-I", url],
            capture_output=True,
            text=True
        )
        elapsed = round(time.time() - start, 3)
        text = (r.stdout + r.stderr).lower()
        ok = ("200 ok" in text or "content-type" in text or "mpegurl" in text or "application" in text)
        return ok, elapsed
    except Exception:
        return False, round(time.time() - start, 3)

query = " ".join(sys.argv[1:]).strip()
if not query:
    print("Usage: python scan_candidates.py USA Network")
    raise SystemExit(1)

q = clean(query)

matches = []
for name, info, url in parse_m3u(FULL):
    blob = clean(name + " " + info + " " + url)
    if q in blob:
        matches.append((name, info, url))

print(f"Found {len(matches)} candidates for: {query}")
print()

results = []
for name, info, url in matches[:80]:
    print(f"Testing {name}...")
    ok, seconds = test_url(url)
    results.append((ok, seconds, name, url))
    print(f"  {'OK' if ok else 'BAD'} {seconds}s")
    print(f"  {url}")

print()
print("BEST:")
for ok, seconds, name, url in sorted(results, key=lambda x: (not x[0], x[1]))[:20]:
    print(f"{'OK ' if ok else 'BAD'} {seconds:5}s | {name} | {url}")
