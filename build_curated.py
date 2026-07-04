from pathlib import Path
import re

SOURCE = Path("output/BrandenTV-Stremio.m3u")
KEYWORDS = Path("curated_keywords.txt")
OUT = Path("docs/BrandenTV-CURATED.m3u")

bad = [
    "spanish","español","latino","latina","univision","telemundo",
    "estrella","tudn","vix","mexico","latin america","portuguese",
    "japan","japanese","テレビ","geo-blocked","backup","test","xxx","adult"
]

keys = [x.strip().lower() for x in KEYWORDS.read_text(errors="ignore").splitlines() if x.strip()]

def clean(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def score(info):
    t = info.lower()
    s = 0
    if "1080" in t: s += 100
    if "720" in t: s += 70
    if "hd" in t: s += 30
    if "usa" in t or "united states" in t: s += 30
    if any(b in t for b in bad): s -= 999
    return s

lines = SOURCE.read_text(errors="ignore").splitlines()
picked = {}

i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        info = lines[i].strip()
        url = lines[i+1].strip() if i+1 < len(lines) else ""
        name = info.split(",")[-1].strip()
        cname = clean(name)

        for k in keys:
            ck = clean(k)
            if cname == ck or ck in cname:
                sc = score(info + " " + url)
                if sc >= 0 and (k not in picked or sc > picked[k][0]):
                    picked[k] = (sc, info, url, name)
        i += 2
    else:
        i += 1

OUT.parent.mkdir(exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    f.write("#EXTM3U\n\n")
    for k in keys:
        if k in picked:
            _, info, url, name = picked[k]
            f.write(info + "\n")
            f.write(url + "\n")

print(f"Created {OUT} with {len(picked)} channels")
for k in keys:
    if k in picked:
        print(f"OK   {k} -> {picked[k][3]}")
    else:
        print(f"MISS {k}")
