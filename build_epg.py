from pathlib import Path
import re, html, json, gzip, urllib.request
import xml.etree.ElementTree as ET

PLAYLIST = Path("output/BrandenTV-Stremio.m3u")
OUT = Path("docs/BrandenTV.xml")
SOURCES = Path("epg_sources.json")
IDENTITY = Path("epg_identity.json")

def attr(line, key):
    m = re.search(rf'{key}="([^"]*)"', line)
    return m.group(1).strip() if m else ""

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

def quality_penalty(text):
    t = " " + (text or "").lower() + " "
    penalty = 0

    bad_regions = [
        ".br@", ".it", ".mx", ".ru", ".sa", ".ar", ".cl", ".pt", ".nz",
        " brazil", " brasil", " italy", " mexico", " russia", " arabia",
        " latin", " latam", " panregional", " internacional"
    ]
    for bad in bad_regions:
        if bad in t:
            penalty -= 1000

    if " us" in t or ".us" in t or "usa" in t or "united states" in t:
        penalty += 40

    if " east" in t:
        penalty += 15
    if " west" in t:
        penalty -= 25

    return penalty

identity = json.load(open(IDENTITY)) if IDENTITY.exists() else {"channels": {}}
id_channels = identity.get("channels", {})

channel_rows = []
name_to_tvg = {}
tvg_to_name = {}
alias_to_tvg = {}
rejects_by_tvg = {}

for line in PLAYLIST.read_text(errors="ignore").splitlines():
    if not line.startswith("#EXTINF"):
        continue

    tvg_id = attr(line, "tvg-id")
    logo = attr(line, "tvg-logo")
    name = line.split(",", 1)[-1].strip()

    if not tvg_id:
        tvg_id = re.sub(r"[^A-Za-z0-9]+", ".", name).strip(".") + ".branden"

    channel_rows.append((tvg_id, name, logo))
    name_to_tvg[norm(name)] = tvg_id
    tvg_to_name[tvg_id] = name

    info = id_channels.get(name, {})
    aliases = set(info.get("aliases", []))
    aliases.add(name)

    station = info.get("station")
    if station:
        aliases.add(station)
        aliases.add(station + "-DT")
        aliases.add(station + "TV")

    for a in aliases:
        alias_to_tvg[norm(a)] = tvg_id

    rejects_by_tvg[tvg_id] = [norm(x) for x in info.get("reject", [])]

def score_match(tvg_id, possible_text):
    name = tvg_to_name.get(tvg_id, "")
    info = id_channels.get(name, {})
    text = " ".join(possible_text)
    clean = norm(text)

    score = 0

    for bad in rejects_by_tvg.get(tvg_id, []):
        if bad and bad in clean:
            return -9999

    nname = norm(name)
    if len(nname) >= 3 and nname in clean:
        score += 100
    elif nname == clean:
        score += 100

    for a in info.get("aliases", []):
        na = norm(a)
        if len(na) >= 3 and na in clean:
            score += 90
        elif na == clean:
            score += 90

    station = info.get("station")
    if station and norm(station) in clean:
        score += 150

    market = info.get("market")
    if market and norm(market) in clean:
        score += 70

    feed = info.get("feed", "east").lower()
    if feed == "east":
        if "east" in clean:
            score += 30
        if "west" in clean:
            score -= 80
    elif feed == "west":
        if "west" in clean:
            score += 30
        if "east" in clean:
            score -= 50

    score += quality_penalty(text)
    return score

out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="BrandenTV">']
programmes = []
matched = {}

for source, url in json.load(open(SOURCES)).items():
    print("Downloading EPG", source)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=30).read()
        if url.endswith(".gz"):
            data = gzip.decompress(data)

        root = ET.fromstring(data)
        source_to_tvg = {}

        for ch in root.findall("channel"):
            cid = ch.attrib.get("id", "")
            names = [x.text or "" for x in ch.findall("display-name")]
            possible = [cid] + names

            best_tvg = None
            best_score = 0

            for item in possible:
                key = norm(item)
                if key in alias_to_tvg:
                    tvg = alias_to_tvg[key]
                    sc = score_match(tvg, possible) + 100
                    if sc > best_score:
                        best_tvg = tvg
                        best_score = sc

            # fallback contains-match
            if not best_tvg:
                for tvg in tvg_to_name:
                    sc = score_match(tvg, possible)
                    if sc > best_score:
                        best_tvg = tvg
                        best_score = sc

            if best_tvg and best_score >= 160:
                source_to_tvg[cid] = best_tvg
                matched[best_tvg] = source

        added = 0
        for prog in root.findall("programme"):
            cid = prog.attrib.get("channel", "")
            if cid in source_to_tvg:
                prog.attrib["channel"] = source_to_tvg[cid]
                programmes.append(ET.tostring(prog, encoding="unicode"))
                added += 1

        print("  matched channels:", len(set(source_to_tvg.values())), "programmes added:", added)

    except Exception as e:
        print("  FAILED", source, e)

seen = set()
for tvg_id, name, logo in channel_rows:
    if tvg_id in seen:
        continue
    seen.add(tvg_id)
    out.append(f'  <channel id="{html.escape(tvg_id, quote=True)}">')
    out.append(f'    <display-name>{html.escape(name)}</display-name>')
    if logo:
        out.append(f'    <icon src="{html.escape(logo, quote=True)}" />')
    out.append("  </channel>")

out.extend(programmes)
out.append("</tv>")

OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Wrote", OUT)
print("Channels:", len(seen))
print("Programmes:", len(programmes))
print("Matched playlist channels:", len(matched))
