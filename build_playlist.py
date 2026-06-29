import json, re, glob
from pathlib import Path
import requests

OUT = Path("output/BrandenTV.m3u")

def parse_m3u(text, source):
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            info = lines[i].strip()
            url = lines[i+1].strip() if i + 1 < len(lines) else ""
            name = info.split(",")[-1].strip()
            if url.startswith("http"):
                out.append({"name": name, "info": info, "url": url, "source": source})
            i += 2
        else:
            i += 1
    return out

def clean_key(name):
    name = name.lower()
    name = re.sub(r"\b(hd|fhd|uhd|4k|1080p|720p|576p|540p|480p|360p|sd|usa|us)\b", "", name)
    name = re.sub(r"\b(live|channel|tv)\b", "", name)
    name = re.sub(r"\b\d+\b$", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return name.strip()

sources = json.load(open("sources.json"))
favorites = [x.strip().lower() for x in open("favorites.txt") if x.strip()]

all_channels = []

for name, url in sources.items():
    print(f"Downloading {name}...")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        all_channels += parse_m3u(r.text, name)
    except Exception as e:
        print(f"FAILED {name}: {e}")

for file in glob.glob("playlists/*.m3u*"):
    print(f"Loading local {file}...")
    text = Path(file).read_text(errors="ignore")
    all_channels += parse_m3u(text, Path(file).stem)

deduped = {}
for ch in all_channels:
    key = clean_key(ch["name"])
    if key and key not in deduped:
        deduped[key] = ch

channels = list(deduped.values())

fav = []
other = []

for ch in channels:
    n = ch["name"].lower()
    if any(f in n for f in favorites):
        fav.append(ch)
    else:
        other.append(ch)

OUT.parent.mkdir(exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    f.write("#EXTM3U\n\n")
    f.write("# ===== FAVORITES =====\n")
    for ch in fav:
        f.write(ch["info"] + "\n" + ch["url"] + "\n")
    f.write("\n# ===== ALL CHANNELS =====\n")
    for ch in other:
        f.write(ch["info"] + "\n" + ch["url"] + "\n")

print("\nDONE")
print(f"Total raw channels: {len(all_channels)}")
print(f"After dedupe: {len(channels)}")
print(f"Favorites: {len(fav)}")
print(f"Created: {OUT}")
