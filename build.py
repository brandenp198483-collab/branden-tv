from pathlib import Path
import re, shutil

SOURCE_FILES = [
    ("IPTV", "BrandenTV-news.m3u", 100),
    ("IPTV", "BrandenTV-kids.m3u", 100),
    ("IPTV", "BrandenTV-sports.m3u", 100),
    ("IPTV", "BrandenTV-movies.m3u", 100),
    ("IPTV", "BrandenTV-other.m3u", 100),
    ("Tablo", "sources/tablo.m3u", 40),
]

CHANNELS = {
    "Entertainment": ["A&E","AMC","BBC America","BET","Bravo","Comedy Central","E!","Freeform","FX","FXX","Hallmark Channel","Lifetime","Lifetime Movie Network","LMN","Paramount Network","Syfy","TBS","TNT","TruTV","TV Land","USA Network","WE tv","MeTV","MeTV Toons","Catchy Comedy","Antenna TV","Cozi TV","Movies!","Story Television","Start TV","Heroes & Icons","Comet","Charge!","Dabl","Retro TV","ION","ION Mystery"],
    "News": ["ABC","CBS","NBC","FOX","Bloomberg TV","CNBC","CNN","Fox Business","Fox News","HLN","Newsmax","NewsNation","The Weather Channel","WeatherNation"],
    "Sports": ["ACC Network","Big Ten Network","CBS Sports Network","ESPN","ESPN2","ESPNews","ESPNU","FS1","FS2","Golf Channel","NBA TV","NFL Network","NHL Network","SEC Network","Tennis Channel","Pac 12 Insider","Pac-12 Insider","Team USA TV","beIN Sports USA","PBR RidePass","PBR: Ride Pass","SportsGrid","Outside TV","Real Madrid TV"],
    "Documentary": ["Animal Planet","Discovery Channel","Discovery Family","Discovery Life","Food Network","HGTV","History Channel","H2","History 365","Investigation Discovery","Magnolia Network","MotorTrend","Nat Geo Wild","National Geographic","Science Channel","Smithsonian Channel","TLC","Travel Channel"],
    "Movies": ["AMC Thrillers","B4U Movies USA","Brividy Cinema","Hallmark Movies & More","Holiday Movie Favorites by Lifetime","Lifetime Movie Favorites","Lifetime Movies","Lifetime Movies Love & Drama","Lifetime Movies: Black Stories","Movie Hub Holiday","Wild Side TV"],
    "Kids": ["Boomerang","Cartoon Network","Disney Channel","Disney Junior","Disney XD","Nick Jr.","Nickelodeon","Nicktoons","PBS Kids"],
    "Music": ["BET Jams","BET Soul","CMT","MTV","MTV2","MTV Classic","VH1"],
    "Spanish / Latino": ["Estrella TV","Fox Deportes","Galavisión","Telemundo","TeleXitos","UniMás","Univision"],
}

FAST_KEEP = True

BAD = [
    "uk","canada","portugal","portuguese","turkey","turkish",
    "china","chinese","japan","japanese","arabic","morocco",
    "latino","spanish","espanol","español",
    "adult","xxx","porn","test","backup","vip","ppv","vod","24/7","24-7",
    "intervention","bravo kids","arryadia","テレビ","geo-blocked","warfare now",
    "idaho","boise" ,"latin america","tbsテレビ", "seoul","テレビ","kids tv","boxing","warfare","untold","time","movies","arryadia","geo-blocked"
]
QUALITY = [("4k",80),("uhd",75),("fhd",70),("1080",65),("hd",55),("720",45),("sd",20)]
GOOD = ["usa","us","u.s.","united states","english","en","east","west"]

ALIASES = {
    "A&E":[r"^a\s*&\s*e(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "E!":[r"^e!(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "TBS":[r"^tbs(\s*\(?\d+p\)?|\s*hd|\s*fhd|\s*east|\s*west)?$"],
    "TNT":[r"^tnt(\s*\(?\d+p\)?|\s*hd|\s*fhd|\s*east|\s*west)?$"],
    "Lifetime":[r"^lifetime(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "History Channel":[r"^history(\s*channel)?(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "HBO":[r"^hbo(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "Starz":[r"^starz(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "ION":[r"^ion(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
    "ION Mystery":[r"^ion\s*mystery(\s*\(?\d+p\)?|\s*hd|\s*fhd)?$"],
}

def norm(s):
    return re.sub(r"[^a-z0-9&]+", " ", s.lower()).strip()

def parse_m3u(path):
    info = None
    for raw in Path(path).read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif info and line and not line.startswith("#"):
            yield info, line
            info = None

def name(info):
    return info.split(",",1)[1].strip() if "," in info else "Channel"

def match(raw, wanted):
    rn = norm(raw)
    if wanted in ALIASES:
        return any(re.search(p, rn, re.I) for p in ALIASES[wanted])
    return re.search(rf"\b{re.escape(norm(wanted))}\b", rn) is not None

def score(info, url, wanted, source_bonus):
    text = norm(info + " " + url)
    s = source_bonus

    for q,v in QUALITY:
        if q in text: s += v
    for g in GOOD:
        if re.search(rf"\b{re.escape(g)}\b", text): s += 40
    for b in BAD:
        if re.search(rf"\b{re.escape(b)}\b", text): s -= 700

    raw = norm(name(info))
    want = norm(wanted)
    if raw == want: s += 250
    elif want in raw: s += 125

    if any(x in text for x in ["latino","spanish","espanol","español"]):
        if wanted not in CHANNELS["Spanish / Latino"] and wanted != "HBO Latino":
            s -= 700

    return s

def rewrite(info, group, wanted):
    if 'group-title="' in info:
        info = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', info)
    else:
        info = info.replace("#EXTINF:", f'#EXTINF:-1 group-title="{group}" ', 1)
    return re.sub(r",(.*)$", f",{wanted}", info)

picked = {}
report = []

for source_name, path, bonus in SOURCE_FILES:
    if not Path(path).exists():
        report.append(f"Missing source: {path}")
        continue

    for info, url in parse_m3u(path):
        raw = name(info)

        for group, wanteds in CHANNELS.items():
            for wanted in wanteds:
                if match(raw, wanted):
                    key = wanted.lower()
                    s = score(info, url, wanted, bonus)
                    if key not in picked or s > picked[key]["score"]:
                        picked[key] = dict(group=group, name=wanted, info=rewrite(info, group, wanted), url=url, score=s, raw=raw, source=source_name)

        if source_name == "Tablo" and FAST_KEEP:
            fast_name = raw.strip()
            key = "fast:" + norm(fast_name)
            if key not in picked:
                picked[key] = dict(group="FAST Live", name=fast_name, info=rewrite(info, "FAST Live", fast_name), url=url, score=10, raw=raw, source="Tablo")

groups = list(CHANNELS.keys()) + ["FAST Live"]
ordered = sorted(
    [x for x in picked.values() if x["score"] >= 0],
    key=lambda x: (groups.index(x["group"]) if x["group"] in groups else 99, x["name"].lower())
)

out = ["#EXTM3U"]
for ch in ordered:
    out += [ch["info"], ch["url"]]

Path("output/BrandenTV-PREFERRED.m3u").write_text("\n".join(out) + "\n")
shutil.copy("output/BrandenTV-PREFERRED.m3u", "docs/BrandenTV-PREFERRED.m3u")

lines = [f"Created BrandenTV-PREFERRED.m3u with {len(ordered)} channels\n"]
for g in groups:
    lines.append(f"{g}: {sum(1 for x in ordered if x['group']==g)}")

lines.append("\nPicked streams:")
for ch in ordered:
    lines.append(f"{ch['group']:16} {ch['name']:32} {ch['source']:7} score={ch['score']:4} raw={ch['raw']}")

Path("output/build_report.txt").write_text("\n".join(lines) + "\n")
shutil.copy("output/build_report.txt", "docs/build_report.txt")

print("\n".join(lines[:20]))
print("\nWrote docs/BrandenTV-PREFERRED.m3u")
print("Wrote docs/build_report.txt")
