import json, re, glob
from pathlib import Path
import requests

HEALTH = json.load(open("candidate_health.json")) if Path("candidate_health.json").exists() else {}
HEALED = json.load(open("healed_overrides.json")) if Path("healed_overrides.json").exists() else {}

OUTPUT_DIR = Path("output")
DOCS_DIR = Path("docs")
FULL_OUT = OUTPUT_DIR / "BrandenTV-Full.m3u"
STREMIO_OUT = OUTPUT_DIR / "BrandenTV-Stremio.m3u"
REPORT_OUT = DOCS_DIR / "whitelist_report.txt"

def clean(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def load_sources():
    sources = json.load(open("sources.json"))
    channels = []
    for source, url in sources.items():
        print(f"Downloading {source}...")
        try:
            r = requests.get(url, timeout=35)
            r.raise_for_status()
            channels += parse_m3u(r.text, source)
        except Exception as e:
            print(f"FAILED {source}: {e}")

    for file in glob.glob("playlists/*.m3u*"):
        print(f"Loading local {file}...")
        channels += parse_m3u(Path(file).read_text(errors="ignore"), Path(file).stem)

    return channels

def parse_m3u(text, source):
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("#EXTINF"):
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
            if url:
                out.append({"name": name, "info": info, "url": url, "source": source})
            i = j + 1
        else:
            i += 1
    return out

def resolution_score(text):
    t = text.lower()
    if "4k" in t or "2160" in t: return 220
    if "1080" in t: return 180
    if "720" in t: return 120
    if "576" in t: return 50
    if "480" in t: return 35
    if "360" in t: return 10
    return 0

def source_score(source):
    return {
        "iptv_org": 140,
        "tablo": 135,
        "ota_diginets": 130,
        "pluto": 100,
        "samsung": 95,
        "plex": 90,
        "roku_online": 85,
        "tubi": 80,
        "xumo": 75,
        "lg": 70,
        "vizio": 65,
        "localnow": 60,
        "free_tv": 45
    }.get(source, 50)

def is_rejected(ch, wanted, db):
    text = clean(ch["name"] + " " + ch["info"] + " " + ch["url"])
    wanted_clean = clean(wanted)

    allowed_spanish = [clean(x) for x in db.get("spanish_allowed", [])]

    for bad in db.get("global_reject", []):
        b = clean(bad)
        if not b:
            continue
        if b in text and wanted_clean not in allowed_spanish:
            return True

    for bad in db.get("specific_reject", {}).get(wanted, []):
        if clean(bad) in text:
            return True

    return False

def aliases_for(wanted, db):
    aliases = [wanted]
    aliases += db.get("aliases", {}).get(wanted, [])
    return list(dict.fromkeys(aliases))

def match_channel(ch, wanted, db):
    cname = clean(ch["name"])

    for alias in aliases_for(wanted, db):
        a = clean(alias)

        if cname == a:
            return True

        if cname in (a + " hd", a + " fhd", a + " 1080p", a + " 720p"):
            return True

        if cname.startswith(a + " ") and any(x in cname for x in ["1080p", "720p", "hd", "east", "west"]):
            return True

    return False

def score_channel(ch, wanted, db):
    text = ch["name"] + " " + ch["info"] + " " + ch["url"]
    cname = clean(ch["name"])
    wanted_clean = clean(wanted)

    health = HEALTH.get(ch["url"], {})
    score = source_score(ch["source"]) + resolution_score(text)

    if health:
        if health.get("ok"):
            score += 1000
            score += max(0, 500 - int(float(health.get("seconds", 5)) * 100))
        else:
            score -= 2000

    if cname == wanted_clean:
        score += 400
    elif any(cname == clean(a) for a in aliases_for(wanted, db)):
        score += 350
    elif wanted_clean in cname:
        score += 80

    if any(x in clean(text) for x in ["usa", "united states", " east", " west"]):
        score += 80

    if "not 24 7" in clean(text):
        score -= 120

    return score

def rewrite(info, group, wanted):
    if 'group-title="' in info:
        info = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', info)
    else:
        info = info.replace("#EXTINF:", f'#EXTINF:-1 group-title="{group}" ', 1)
    return re.sub(r",(.*)$", f",{wanted}", info)

db = json.load(open("channel_whitelist.json"))
all_channels = load_sources()

seen_urls = set()
full = []
for ch in all_channels:
    if ch["url"] not in seen_urls:
        seen_urls.add(ch["url"])
        full.append(ch)

picked = []
report = []
total_wanted = 0

for group, names in db["categories"].items():
    for wanted in names:
        total_wanted += 1

        healed = HEALED.get(wanted)
        if healed and healed.get("ok"):
            ch = {
                "name": healed["raw"],
                "info": healed["info"],
                "url": healed["url"],
                "source": healed["source"]
            }
            score = healed.get("score", 999999)
        else:
            candidates = []
            for ch in full:
                if match_channel(ch, wanted, db) and not is_rejected(ch, wanted, db):
                    candidates.append((score_channel(ch, wanted, db), ch))

            if not candidates:
                report.append(f"MISS  | {group} | {wanted}")
                continue

            candidates.sort(key=lambda x: x[0], reverse=True)
            score, ch = candidates[0]

        picked.append({
            "group": group,
            "name": wanted,
            "info": rewrite(ch["info"], group, wanted),
            "url": ch["url"],
            "raw": ch["name"],
            "source": ch["source"],
            "score": score
        })
        report.append(f"FOUND | {group} | {wanted} | {ch['source']} | score={score} | raw={ch['name']}")

OUTPUT_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

def write_m3u(path, channels):
    with path.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for ch in channels:
            f.write(ch["info"] + "\n")
            f.write(ch["url"] + "\n")

write_m3u(FULL_OUT, full)
write_m3u(STREMIO_OUT, picked)
write_m3u(DOCS_DIR / "BrandenTV-Stremio.m3u", picked)
write_m3u(DOCS_DIR / "BrandenTV.m3u", picked)

REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")

print("\nDONE")
print(f"Raw channels: {len(all_channels)}")
print(f"Full unique channels: {len(full)}")
print(f"Whitelist channels wanted: {total_wanted}")
print(f"Whitelist channels found: {len(picked)}")
print(f"Created: {STREMIO_OUT}")
print(f"Report: {REPORT_OUT}")
