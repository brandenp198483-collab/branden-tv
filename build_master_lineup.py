from pathlib import Path
import re

SOURCE_FILES = [
    "BrandenTV-news.m3u",
    "BrandenTV-kids.m3u",
    "BrandenTV-sports.m3u",
    "BrandenTV-movies.m3u",
    "BrandenTV-other.m3u",
]

CHANNELS = {
"Entertainment": ["A&E","Adult Swim","AMC","AXS TV","BBC America","BET","BET Her","Bounce TV","Bravo","Cleo TV","Comedy Central","Comedy.TV","Comet","Cozi TV","CW","Dove Channel","E!","Freeform","Fuse","FX","FXX","Great American Family","Great American Living","Grit TV","Hallmark Channel","Hallmark Drama","Hallmark Movies & Mysteries","IFC","INSP","ION","ION Mystery","ION Plus","Lifetime","Lifetime Movie Network","LMN","Logo TV","MeTV","MeTV+","MyNetworkTV","OWN","Oxygen","Paramount Network","Pop TV","Reelz","Retro TV","Sundance TV","Syfy","TBS","TNT","TruTV","TV Land","TV One","UPtv","USA Network","VH1","Vice TV","WE tv"],
"News": ["ABC","CBS","NBC","FOX","BBC World News","Bloomberg TV","CNBC","CNN","CNN International","Court TV","Fox Business","Fox News","HLN","Newsmax","NewsNation","The Weather Channel","WeatherNation"],
"Sports": ["ACC Network","Big Ten Network","BTN","CBS Sports Network","ESPN","ESPN2","ESPNews","ESPNU","FanDuel TV","Fox Sports 1","FS1","Fox Sports 2","FS2","Golf Channel","NBA TV","NBC Sports","NFL Network","NHL Network","Olympic Channel","Outdoor Channel","Pursuit Channel","SEC Network","Sportsman Channel","Tennis Channel"],
"Documentary": ["American Heroes Channel","Animal Planet","Destination America","Discovery Channel","Discovery Family","Discovery Life","DIY Network","Food Network","Cooking Channel","HGTV","History Channel","H2","History 365","Investigation Discovery","ID","Magnolia Network","MotorTrend","Nat Geo Wild","National Geographic","Science Channel","Smithsonian Channel","TLC","Travel Channel"],
"Movies": ["ActionMAX","Cinemax","Family Movie Classics","FMC","FX Movie Channel","FXM","HBO","HBO 2","HBO Comedy","HBO Family","HBO Latino","HBO Signature","HBO Zone","MovieMAX","Showtime","Showtime 2","Showtime Extreme","Showtime Family","Showtime Next","Showtime Showcase","Showtime Women","Starz","Starz Cinema","Starz Comedy","Starz Edge","Starz Encore","Starz Encore Action","Starz Encore Black","Starz Encore Classic","Starz Encore Family","Starz Encore Suspense","Starz Encore Westerns","Starz in Black","Starz Kids & Family","TCM"],
"Kids": ["Boomerang","Cartoon Network","Disney Channel","Disney Junior","Disney XD","Nick Jr.","Nickelodeon","Nicktoons","PBS Kids","Universal Kids"],
"Music": ["BET Jams","BET Soul","CMT","MTV","MTV2","MTV Classic","MTV Live","MTVU"],
"Spanish / Latino": ["Estrella TV","Fox Deportes","Galavisión","Telemundo","TeleXitos","UniMás","Univision"],
"Shopping / Religious": ["EWTN","HSN","Jewelry TV","JTV","QVC","QVC2","TBN","Victory Channel"],
"FAST / Local": ["Antenna TV","PBS","Tubi","Family Entertainment TV","FETV","RFD-TV"],
}

BAD = [
    "uk","united kingdom","canada","australia","india","france","germany","spain","italy",
    "mexico","brazil","argentina","colombia","chile","portugal","portuguese","turkey",
    "turkish","french","german","italian","arab","arabic","china","chinese","korea",
    "korean","japan","japanese","adult xxx","porn","test","backup","vip","ppv","vod",
    "24/7","24-7"
]

GOOD = ["usa","us","u.s.","united states","english","en","east","west"]
QUALITY = [("4k",80),("uhd",75),("fhd",70),("1080",65),("hd",55),("720",45),("sd",20)]

ALIASES = {
    "A&E": [r"\ba\s*&\s*e\b", r"\ba&e\b"],
    "USA Network": [r"\busa network\b", r"\busa\b"],
    "Big Ten Network": [r"\bbig ten network\b", r"\bbtn\b"],
    "BTN": [r"\bbtn\b", r"\bbig ten network\b"],
    "Fox Sports 1": [r"\bfox sports 1\b", r"\bfs1\b"],
    "FS1": [r"\bfs1\b", r"\bfox sports 1\b"],
    "Fox Sports 2": [r"\bfox sports 2\b", r"\bfs2\b"],
    "FS2": [r"\bfs2\b", r"\bfox sports 2\b"],
    "Lifetime Movie Network": [r"\blifetime movie network\b", r"\blmn\b"],
    "LMN": [r"\blmn\b", r"\blifetime movie network\b"],
    "Investigation Discovery": [r"\binvestigation discovery\b", r"\bid\b"],
    "ID": [r"\bid\b", r"\binvestigation discovery\b"],
    "Family Movie Classics": [r"\bfamily movie classics\b", r"\bfmc\b"],
    "FMC": [r"\bfmc\b", r"\bfamily movie classics\b"],
    "FX Movie Channel": [r"\bfx movie channel\b", r"\bfxm\b"],
    "FXM": [r"\bfxm\b", r"\bfx movie channel\b"],
    "Family Entertainment TV": [r"\bfamily entertainment tv\b", r"\bfetv\b"],
    "FETV": [r"\bfetv\b", r"\bfamily entertainment tv\b"],
    "The Weather Channel": [r"\bthe weather channel\b", r"\bweather channel\b"],
    "History Channel": [r"\bhistory channel\b", r"\bhistory\b"],
}

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
    return re.sub(r"[^a-z0-9&]+", " ", s.lower()).strip()

def match_channel(raw_name, wanted):
    rn = norm(raw_name)
    if wanted in ALIASES:
        return any(re.search(p, rn, re.I) for p in ALIASES[wanted])
    return re.search(rf"\b{re.escape(norm(wanted))}\b", rn) is not None

def score(info, url, wanted):
    text = f"{info} {url}".lower()
    nt = norm(text)
    s = 0

    for q, v in QUALITY:
        if q in nt:
            s += v

    for g in GOOD:
        if re.search(rf"\b{re.escape(g)}\b", nt):
            s += 40

    for b in BAD:
        if re.search(rf"\b{re.escape(b)}\b", nt):
            s -= 600

    raw = norm(name_from_info(info))
    want = norm(wanted)

    if raw == want:
        s += 200
    elif want in raw:
        s += 100

    # allow SD, but punish non-English/international harder
    if "latino" in nt or "spanish" in nt or "espanol" in nt or "español" in nt:
        if wanted not in CHANNELS["Spanish / Latino"] and wanted != "HBO Latino":
            s -= 600

    return s

def write_info(info, group, wanted):
    if 'group-title="' in info:
        info = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', info)
    else:
        info = info.replace("#EXTINF:", f'#EXTINF:-1 group-title="{group}" ', 1)
    return re.sub(r",(.*)$", f",{wanted}", info)

candidates = {}

for file in SOURCE_FILES:
    if not Path(file).exists():
        continue
    for info, url in parse_entries(Path(file).read_text(errors="ignore")):
        raw = name_from_info(info)

        for group, wanted_list in CHANNELS.items():
            for wanted in wanted_list:
                if match_channel(raw, wanted):
                    key = wanted.lower()
                    s = score(info, url, wanted)
                    cur = candidates.get(key)

                    if cur is None or s > cur["score"]:
                        candidates[key] = {
                            "group": group,
                            "name": wanted,
                            "score": s,
                            "raw": raw,
                            "info": write_info(info, group, wanted),
                            "url": url,
                        }

ordered = sorted(candidates.values(), key=lambda x: (list(CHANNELS.keys()).index(x["group"]), x["name"]))

out = ["#EXTM3U"]
for ch in ordered:
    # Skip terrible matches only
    if ch["score"] < -300:
        continue
    out.append(ch["info"])
    out.append(ch["url"])

Path("BrandenTV-MASTER.m3u").write_text("\n".join(out) + "\n")

print(f"Created BrandenTV-MASTER.m3u with {len(out)//2} channels")
for group in CHANNELS:
    print(group, sum(1 for c in ordered if c["group"] == group and c["score"] >= -300))

print("\nPicked streams:")
for c in ordered:
    if c["score"] >= -300:
        print(f"{c['group']:20} {c['name']:30} score={c['score']:5} raw={c['raw']}")
