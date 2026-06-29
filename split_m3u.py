from pathlib import Path

src = Path("output/BrandenTV-Stremio.m3u")
out = Path("output/categories")
out.mkdir(parents=True, exist_ok=True)

cats = {
    "news": ["news", "bloomberg", "cbsn", "cnn", "fox", "msnbc", "weather"],
    "kids": ["kids", "cartoon", "disney", "nick", "barbie"],
    "sports": ["sports", "espn", "nfl", "nba", "mlb", "nhl", "ufc"],
    "movies": ["movie", "cinema", "film"],
}

text = src.read_text(errors="ignore").splitlines()
entries = []
cur = []
for line in text:
    if line.startswith("#EXTINF") and cur:
        entries.append(cur)
        cur = []
    cur.append(line)
if cur:
    entries.append(cur)

header = "#EXTM3U\n"
buckets = {k: [] for k in cats}
buckets["other"] = []

for e in entries:
    joined = " ".join(e).lower()
    placed = False
    for cat, words in cats.items():
        if any(w in joined for w in words):
            buckets[cat].append(e)
            placed = True
            break
    if not placed:
        buckets["other"].append(e)

for cat, items in buckets.items():
    p = out / f"BrandenTV-{cat}.m3u"
    p.write_text(header + "\n".join("\n".join(i) for i in items))
    print(cat, len(items), p)

