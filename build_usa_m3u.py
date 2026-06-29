from pathlib import Path
import re

SOURCE_FILES = [
    "BrandenTV-news.m3u",
    "BrandenTV-kids.m3u",
    "BrandenTV-sports.m3u",
    "BrandenTV-movies.m3u",
    "BrandenTV-other.m3u",
]

REMOVE_WORDS = [
    " uk ", " united kingdom", " canada", " ca |", " ca:", " australia",
    " india", " france", " germany", " spain", " italy", " mexico",
    " arabic", " turkey", " portuguese", " brazil", " latino", " chile",
    " argentina", " colombia", " pakistan", " africa", " africa",
    " adult", " xxx", " porn",
    " test", " backup", " back up", " vip", " ppv", " vod",
    " 24/7", "24-7", " loop", " event", " events",
    " shopping", " qvc", " hsn",
]

QUALITY_SCORE = {
    "4k": 50,
    "uhd": 45,
    "fhd": 40,
    "1080": 35,
    "hd": 30,
    "720": 25,
    "sd": 10,
}

CATEGORY_RULES = [
    ("News", ["cnn", "fox news", "msnbc", "cnbc", "bloomberg", "newsmax", "weather", "c-span"]),
    ("Sports", ["espn", "fs1", "fs2", "nfl", "nba", "mlb", "nhl", "golf", "tennis", "bein", "sec network"]),
    ("Kids", ["disney", "nick", "cartoon", "boomerang", "pbs kids", "babyfirst"]),
    ("Movies", ["hbo", "showtime", "starz", "cinemax", "movie", "movies", "mgm"]),
    ("Entertainment", ["tnt", "tbs", "usa network", "fx", "fxx", "amc", "a&e", "bravo", "comedy", "paramount", "syfy"]),
    ("Documentary", ["history", "discovery", "national geographic", "nat geo", "science", "smithsonian", "animal planet"]),
    ("Music", ["mtv", "vh1", "music", "bet jams", "cmt"]),
    ("Local", ["abc", "cbs", "nbc", "fox ", "pbs", "cw"]),
]

def parse_entries(text):
    lines = text.splitlines()
    entries = []
    info = None

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif info and line and not line.startswith("#"):
            entries.append((info, line))
            info = None

    return entries

def name_from_extinf(info):
    return info.split(",", 1)[1].strip() if "," in info else "Channel"

def clean_name(name):
    n = name

    n = re.sub(r"^\s*(usa|us|u\.s\.a\.|united states)\s*[\|\-\:\•]\s*", "", n, flags=re.I)
    n = re.sub(r"\b(usa|us)\b", "", n, flags=re.I)
    n = re.sub(r"\b(fhd|hd|sd|uhd|4k|1080p?|720p?)\b", "", n, flags=re.I)
    n = re.sub(r"\b(east|west|backup|vip|raw|feed)\b", "", n, flags=re.I)
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"\s*[\|\-\:\•]\s*$", "", n)
    return n.strip()

def base_key(name):
    n = clean_name(name).lower()
    n = re.sub(r"[^a-z0-9]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

def should_remove(info, url):
    text = f" {info} {url} ".lower()

    # Keep obvious USA markers
    if any(x in text for x in [" usa ", " us |", " us:", " united states"]):
        usa_hint = True
    else:
        usa_hint = False

    for bad in REMOVE_WORDS:
        if bad in text:
            return True

    # Remove obvious non-US prefixes
    if re.search(r"\b(uk|ca|au|in|fr|de|es|it|mx|br)\s*[\|\:\-]", text):
        return True

    return False

def quality(info):
    t = info.lower()
    score = 0
    for word, val in QUALITY_SCORE.items():
        if word in t:
            score = max(score, val)

    # small penalty for junky versions
    for bad in ["backup", "vip", "raw", "feed", "east", "west"]:
        if bad in t:
            score -= 10

    return score

def category_for(name):
    n = name.lower()
    for cat, words in CATEGORY_RULES:
        if any(w in n for w in words):
            return cat
    return "Entertainment"

def rewrite_group(info, group):
    if 'group-title="' in info:
        return re.sub(r'group-title="[^"]*"', f'group-title="{group}"', info)
    return info.replace("#EXTINF:", f'#EXTINF:-1 group-title="{group}" ', 1)

best = {}

for filename in SOURCE_FILES:
    if not Path(filename).exists():
        continue

    for info, url in parse_entries(Path(filename).read_text(errors="ignore")):
        name = name_from_extinf(info)

        if should_remove(info, url):
            continue

        key = base_key(name)
        if not key:
            continue

        score = quality(info)
        current = best.get(key)

        if current is None or score > current["score"]:
            cleaned = clean_name(name)
            group = category_for(cleaned)
            new_info = rewrite_group(info, group)
            new_info = re.sub(r",(.*)$", f",{cleaned}", new_info)

            best[key] = {
                "score": score,
                "name": cleaned,
                "group": group,
                "info": new_info,
                "url": url,
            }

ordered = sorted(best.values(), key=lambda x: (x["group"], x["name"].lower()))

out = ["#EXTM3U"]
for item in ordered:
    out.append(item["info"])
    out.append(item["url"])

Path("BrandenTV-USA.m3u").write_text("\n".join(out) + "\n")

print(f"Created BrandenTV-USA.m3u with {len(ordered)} channels")
for group in sorted(set(i["group"] for i in ordered)):
    print(group, sum(1 for i in ordered if i["group"] == group))
