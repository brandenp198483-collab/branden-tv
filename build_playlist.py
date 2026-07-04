import json
import re
import glob
from pathlib import Path
import requests

OUTPUT_DIR = Path("output")
DOCS_DIR = Path("docs")

FULL_OUT = OUTPUT_DIR / "BrandenTV-Full.m3u"
STREMIO_OUT = OUTPUT_DIR / "BrandenTV-Stremio.m3u"
FAV_OUT = OUTPUT_DIR / "BrandenTV-Favorites.m3u"
WATCH_OUT = OUTPUT_DIR / "premium_watchlist_matches.txt"

def load_lines(path):
    p = Path(path)
    if not p.exists():
        return []
    return [x.strip() for x in p.read_text(errors="ignore").splitlines() if x.strip()]

def parse_resolution(name, info):
    text = f"{name} {info}".lower()
    if "4k" in text or "2160" in text:
        return 2160
    if "1080" in text:
        return 1080
    if "720" in text:
        return 720
    if "576" in text:
        return 576
    if "540" in text:
        return 540
    if "480" in text:
        return 480
    if "360" in text:
        return 360
    return 0

def parse_m3u(text, source):
    lines = text.splitlines()
    channels = []
    i = 0

    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            info = lines[i].strip()
            j = i + 1
            url = ""
            while j < len(lines):
                candidate = lines[j].strip()
                if candidate.startswith("http"):
                    url = candidate
                    break
                if candidate.startswith("#EXTINF"):
                    break
                j += 1

            name = info.split(",")[-1].strip()

            if url.startswith("http"):
                channels.append({
                    "name": name,
                    "info": info,
                    "url": url,
                    "source": source,
                    "resolution": parse_resolution(name, info)
                })
            i += 2
        else:
            i += 1

    return channels

def base_key(name):
    n = name.lower()
    n = re.sub(r"\[[^\]]*\]", " ", n)
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\b(4k|uhd|fhd|hd|sd|1080p|720p|576p|540p|480p|360p)\b", " ", n)
    n = re.sub(r"\b(us|usa|live|channel|tv)\b", " ", n)
    n = re.sub(r"\b\d+\b$", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return n.strip()

def is_match(name, terms):
    n = name.lower()
    return any(term.lower() in n for term in terms)

def source_score(source):
    preferred = {
        "pluto": 100,
        "samsung": 95,
        "plex": 90,
        "roku_online": 85,
        "tubi": 80,
        "xumo": 75,
        "lg": 70,
        "vizio": 65,
        "iptv_org": 50,
        "free_tv": 40
    }
    return preferred.get(source, 30)

def channel_score(ch):
    score = 0
    score += source_score(ch["source"])
    score += ch["resolution"] // 10

    name = ch["name"].lower()
    if "geo-blocked" in name:
        score -= 40
    if "not 24/7" in name:
        score -= 20
    if "backup" in name:
        score -= 5

    return score

def write_m3u(path, channels):
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for ch in channels:
            f.write(ch["info"] + "\n")
            f.write(ch["url"] + "\n")

sources = json.load(open("sources.json"))
favorites = load_lines("favorites.txt")
watchlist = load_lines("premium_watchlist.txt")
stremio_keywords = load_lines("stremio_keywords.txt")

all_channels = []

for name, url in sources.items():
    print(f"Downloading {name}...")
    try:
        r = requests.get(url, timeout=35)
        r.raise_for_status()
        all_channels.extend(parse_m3u(r.text, name))
    except Exception as e:
        print(f"FAILED {name}: {e}")

for file in glob.glob("playlists/*.m3u*"):
    print(f"Loading local {file}...")
    text = Path(file).read_text(errors="ignore")
    all_channels.extend(parse_m3u(text, Path(file).stem))

# Full playlist: light URL dedupe only
seen_urls = set()
full_channels = []
for ch in all_channels:
    if ch["url"] not in seen_urls:
        seen_urls.add(ch["url"])
        full_channels.append(ch)

full_channels.sort(key=channel_score, reverse=True)

# Favorites
favorite_channels = [ch for ch in full_channels if is_match(ch["name"], favorites)]
favorite_channels.sort(key=channel_score, reverse=True)

# Stremio playlist:
# Keep up to 3 versions per base channel, so 1080p / 720p / backup can coexist.
stremio_candidates = [
    ch for ch in full_channels
    if is_match(ch["name"], stremio_keywords) or is_match(ch["name"], favorites)
]

groups = {}
for ch in stremio_candidates:
    key = base_key(ch["name"])
    if key:
        groups.setdefault(key, []).append(ch)

stremio_channels = []
for key, group in groups.items():
    group.sort(key=channel_score, reverse=True)
    stremio_channels.extend(group[:1])

# Favorites first in Stremio
stremio_favs = [ch for ch in stremio_channels if is_match(ch["name"], favorites)]
stremio_other = [ch for ch in stremio_channels if ch not in stremio_favs]
stremio_final = stremio_favs + stremio_other

# Premium/watchlist report
watch_matches = [ch for ch in full_channels if is_match(ch["name"], watchlist)]
with WATCH_OUT.open("w", encoding="utf-8") as f:
    for ch in watch_matches:
        f.write(f'{ch["name"]} | source={ch["source"]} | res={ch["resolution"]} | {ch["url"]}\n')

write_m3u(FULL_OUT, full_channels)
write_m3u(FAV_OUT, favorite_channels)
write_m3u(STREMIO_OUT, stremio_final)

# Backward-compatible old name
write_m3u(OUTPUT_DIR / "BrandenTV.m3u", stremio_final)

DOCS_DIR.mkdir(exist_ok=True)
write_m3u(DOCS_DIR / "BrandenTV.m3u", stremio_final)
write_m3u(DOCS_DIR / "BrandenTV-Stremio.m3u", stremio_final)
write_m3u(DOCS_DIR / "BrandenTV-Full.m3u", full_channels)
write_m3u(DOCS_DIR / "BrandenTV-Favorites.m3u", favorite_channels)
Path(DOCS_DIR / "premium_watchlist_matches.txt").write_text(WATCH_OUT.read_text(errors="ignore"), encoding="utf-8")

print("\nDONE")
print(f"Raw channels: {len(all_channels)}")
print(f"Full channels: {len(full_channels)}")
print(f"Favorites: {len(favorite_channels)}")
print(f"Stremio channels: {len(stremio_final)}")
print(f"Watchlist matches: {len(watch_matches)}")
print(f"Created: {STREMIO_OUT}")
