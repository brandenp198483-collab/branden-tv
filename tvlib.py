import json, re, glob
from pathlib import Path
import requests

def clean(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def parse_m3u_text(text, source):
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
                if candidate.lstrip().startswith("http"):
                    url = candidate.lstrip()
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

def load_all_sources():
    channels = []
    sources = json.load(open("sources.json"))

    for source, url in sources.items():
        print(f"Downloading {source}...")
        try:
            r = requests.get(url, timeout=35)
            r.raise_for_status()
            channels += parse_m3u_text(r.text, source)
        except Exception as e:
            print(f"FAILED {source}: {e}")

    for pattern in ["playlists/*.m3u*", "playlists/incoming/*.m3u*", "playlists/accepted/*.m3u*"]:
        for file in glob.glob(pattern):
            print(f"Loading local {file}...")
            channels += parse_m3u_text(Path(file).read_text(errors="ignore"), Path(file).stem)

    return channels

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

def is_rejected(ch, wanted, db):
    text = clean(ch["name"] + " " + ch["info"] + " " + ch["url"])
    wanted_clean = clean(wanted)

    allowed_spanish = [clean(x) for x in db.get("spanish_allowed", [])]

    for bad in db.get("global_reject", []):
        b = clean(bad)
        if b and b in text and wanted_clean not in allowed_spanish:
            return True

    for bad in db.get("specific_reject", {}).get(wanted, []):
        b = clean(bad)
        if b and b in text:
            return True

    return False
