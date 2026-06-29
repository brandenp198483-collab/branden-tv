import re, json
from pathlib import Path

BASE_URL = "https://brandenp198483-collab.github.io/branden-tv"

CATEGORIES = {
    "news": "BrandenTV News",
    "kids": "BrandenTV Kids",
    "sports": "BrandenTV Sports",
    "movies": "BrandenTV Movies",
    "other": "BrandenTV Other",
}

def parse_m3u(path, cat):
    lines = Path(path).read_text(errors="ignore").splitlines()
    out = []
    extinf = None

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            extinf = line
        elif line and not line.startswith("#") and extinf:
            name_match = re.search(r',(.+)$', extinf)
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            group_match = re.search(r'group-title="([^"]*)"', extinf)

            name = name_match.group(1).strip() if name_match else "Channel"
            logo = logo_match.group(1).strip() if logo_match else ""
            group = group_match.group(1).strip() if group_match else "Live TV"

            safe_id = re.sub(r"[^a-zA-Z0-9]+", "-", f"{cat}-{name}").strip("-").lower()

            out.append({
                "id": safe_id,
                "type": "tv",
                "name": name,
                "poster": logo,
                "posterShape": "square",
                "description": f"{name} - {group}",
                "genres": [group, cat],
                "streams": [{
                    "title": name,
                    "url": line
                }]
            })
            extinf = None

    return out

all_channels = {}

addon_dir = Path("addon")
addon_dir.mkdir(exist_ok=True)

catalogs = []

for cat, title in CATEGORIES.items():
    m3u = Path(f"BrandenTV-{cat}.m3u")
    channels = parse_m3u(m3u, cat)
    all_channels[cat] = channels

    metas = [
        {k: ch[k] for k in ["id", "type", "name", "poster", "posterShape", "description", "genres"]}
        for ch in channels
    ]

    Path(addon_dir / f"catalog-tv-{cat}.json").write_text(
        json.dumps({"metas": metas}, indent=2)
    )

    catalogs.append({
        "type": "tv",
        "id": cat,
        "name": title
    })

for cat, channels in all_channels.items():
    for ch in channels:
        Path(addon_dir / f"stream-tv-{ch['id']}.json").write_text(
            json.dumps({"streams": ch["streams"]}, indent=2)
        )

manifest = {
    "id": "community.brandentv",
    "version": "1.0.0",
    "name": "BrandenTV",
    "description": "Custom BrandenTV live TV channels",
    "resources": ["catalog", "stream"],
    "types": ["tv"],
    "catalogs": catalogs,
    "idPrefixes": ["news-", "kids-", "sports-", "movies-", "other-"],
    "behaviorHints": {
        "configurable": False,
        "configurationRequired": False
    }
}

Path(addon_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

print("Built BrandenTV addon")
for cat, channels in all_channels.items():
    print(cat, len(channels))

print()
print(f"Manifest URL: {BASE_URL}/addon/manifest.json")
