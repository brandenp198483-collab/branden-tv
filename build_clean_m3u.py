from pathlib import Path

files = [
    "BrandenTV-news.m3u",
    "BrandenTV-kids.m3u",
    "BrandenTV-sports.m3u",
    "BrandenTV-movies.m3u",
    "BrandenTV-other.m3u",
]

seen = set()
out = ["#EXTM3U"]

for file in files:
    lines = Path(file).read_text(errors="ignore").splitlines()
    pair = []
    for line in lines:
        if line.startswith("#EXTINF"):
            pair = [line]
        elif pair and line and not line.startswith("#"):
            url = line.strip()
            if url not in seen:
                seen.add(url)
                out.extend(pair)
                out.append(url)
            pair = []

Path("BrandenTV-CLEAN.m3u").write_text("\n".join(out) + "\n")
print(f"Clean playlist created with {len(seen)} channels: BrandenTV-CLEAN.m3u")
