from pathlib import Path
import re

SOURCE_FILES = [
    "BrandenTV-news.m3u",
    "BrandenTV-kids.m3u",
    "BrandenTV-sports.m3u",
    "BrandenTV-movies.m3u",
    "BrandenTV-other.m3u",
]

PREFERRED = {
    "Locals": ["ABC", "CBS", "NBC", "FOX", "CW", "PBS"],
    "Tampa Bay": ["WFLA", "WTSP", "WTVT", "WFTS", "WMOR", "WEDU", "Bay News 9", "Tampa"],
    "News": ["CNN", "Fox News", "MSNBC", "CNBC", "Bloomberg", "Newsmax", "NewsNation", "C-SPAN", "Weather Channel"],
    "Sports": ["ESPN", "ESPN2", "ESPNU", "FS1", "FS2", "NFL Network", "MLB Network", "NBA TV", "NHL Network", "Golf Channel", "Tennis Channel", "SEC Network", "ACC Network", "Big Ten Network"],
    "Entertainment": ["TNT", "TBS", "USA Network", "FX", "FXX", "AMC", "A&E", "Bravo", "Comedy Central", "Paramount Network", "Syfy", "Hallmark", "Lifetime", "HGTV", "Food Network", "TLC", "Travel Channel"],
    "Documentary": ["Discovery", "Science Channel", "History", "National Geographic", "Nat Geo Wild", "Smithsonian", "Animal Planet"],
    "Movies": ["HBO", "HBO 2", "HBO Signature", "Showtime", "Starz", "Cinemax", "MGM"],
    "Kids": ["Disney Channel", "Disney XD", "Disney Junior", "Cartoon Network", "Boomerang", "Nickelodeon", "Nick Jr", "TeenNick", "PBS Kids"],
    "Music": ["MTV", "VH1", "CMT", "BET"],
}

BAD_WORDS = [
    "uk", "canada", "australia", "india", "france", "germany", "spain", "italy",
    "mexico", "brazil", "arabic", "latino", "adult", "xxx", "porn", "test",
    "backup", "vip", "ppv", "vod", "24/7", "24-7", "shopping", "qvc", "hsn"
]

QUALITY = [("4k", 50), ("uhd", 45), ("fhd", 40), ("1080", 35), ("hd", 30), ("720", 25), ("sd", 10)]

def parse_entries(text):
    info = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif info and line and not line.startswith("#"):
            yield info, line
            info = None

def name_from_info(info):
    return info.split(",", 1)[1].strip() if "," in info else "Channel"

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def clean_display_name(name):
    n = re.sub(r"^\s*(usa|us)\s*[\|\-\:\•]\s*", "", name, flags=re.I)
    n = re.sub(r"\b(fhd|hd|sd|uhd|4k|1080p?|720p?)\b", "", n, flags=re.I)
    n = re.sub(r"\b(east|west|backup|vip|feed|raw)\b", "", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" -|:")
    return n

def score(info):
    t = info.lower()
    s = 0
    for q, v in QUALITY:
        if q in t:
            s = max(s, v)
    if "backup" in t or "test" in t or "vip" in t:
        s -= 100
    if "east" in t:
        s += 3
    return s

def bad(info, url):
    t = norm(info + " " + url)
    return any(re.search(rf"\b{re.escape(w)}\b", t) for w in BAD_WORDS)

def matches_channel(raw_name, wanted):
    rn = norm(raw_name)
    wn = norm(wanted)
    return wn in rn

candidates = {}

for file in SOURCE_FILES:
    if not Path(file).exists():
        continue
    for info, url in parse_entries(Path(file).read_text(errors="ignore")):
        raw_name = name_from_info(info)
        if bad(info, url):
            continue

        for group, wanted_list in PREFERRED.items():
            for wanted in wanted_list:
                if matches_channel(raw_name, wanted):
                    key = wanted.lower()
                    item_score = score(info)

                    current = candidates.get(key)
                    if current is None or item_score > current["score"]:
                        new_info = info
                        if 'group-title="' in new_info:
                            new_info = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', new_info)
                        else:
                            new_info = new_info.replace("#EXTINF:", f'#EXTINF:-1 group-title="{group}" ', 1)

                        new_info = re.sub(r",(.*)$", f",{wanted}", new_info)

                        candidates[key] = {
                            "group": group,
                            "name": wanted,
                            "score": item_score,
                            "info": new_info,
                            "url": url,
                        }

ordered = sorted(candidates.values(), key=lambda x: (list(PREFERRED.keys()).index(x["group"]), x["name"]))

out = ["#EXTM3U"]
for item in ordered:
    out.append(item["info"])
    out.append(item["url"])

Path("BrandenTV-PREFERRED.m3u").write_text("\n".join(out) + "\n")

print(f"Created BrandenTV-PREFERRED.m3u with {len(ordered)} channels")
for group in PREFERRED:
    count = sum(1 for i in ordered if i["group"] == group)
    print(group, count)

