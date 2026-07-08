import json, re
from pathlib import Path

PLAYLIST = Path("docs/BrandenTV-Stremio.m3u")
OUT = Path("epg_identity.json")

def attr(line, key):
    m = re.search(rf'{key}="([^"]*)"', line)
    return m.group(1).strip() if m else ""

channels = {}

for line in PLAYLIST.read_text(errors="ignore").splitlines():
    if not line.startswith("#EXTINF"):
        continue

    name = line.split(",", 1)[-1].strip()

    channels[name] = {
        "feed": "east",
        "aliases": [name],
        "reject": [name + " West"]
    }

# Manually strong local identities
overrides = {
    "ABC Tampa": {"station": "WFTS", "market": "Tampa", "network": "ABC", "feed": "local", "aliases": ["WFTS", "WFTS-DT", "ABC Action News", "ABC Tampa"]},
    "FOX Tampa": {"station": "WTVT", "market": "Tampa", "network": "FOX", "feed": "local", "aliases": ["WTVT", "WTVT-DT", "FOX 13 Tampa", "FOX Tampa"]},
    "FOX Philadelphia": {"station": "WTXF", "market": "Philadelphia", "network": "FOX", "feed": "local", "aliases": ["WTXF", "WTXF-DT", "FOX 29", "FOX Philadelphia"]},
    "FOX Boston": {"station": "WFXT", "market": "Boston", "network": "FOX", "feed": "local", "aliases": ["WFXT", "WFXT-DT", "Boston 25", "FOX Boston"]},
    "NBC Boston": {"station": "WBTS", "market": "Boston", "network": "NBC", "feed": "local", "aliases": ["WBTS", "WBTS-CD", "NBC10 Boston", "NBC Boston"]},
    "NBC Philadelphia": {"station": "WCAU", "market": "Philadelphia", "network": "NBC", "feed": "local", "aliases": ["WCAU", "WCAU-DT", "NBC10 Philadelphia", "NBC Philadelphia"]}
}

channels.update(overrides)

data = {
    "defaults": {
        "feed": "east",
        "preferred_markets": ["Tampa", "Philadelphia", "Boston"]
    },
    "channels": channels
}

OUT.write_text(json.dumps(data, indent=2) + "\n")
print("Wrote", OUT)
print("Channels:", len(channels))
