from pathlib import Path
import re, html, json, gzip, urllib.request
import xml.etree.ElementTree as ET

PLAYLIST = Path("docs/BrandenTV-Stremio.m3u")
OUT = Path("docs/BrandenTV.xml")
SOURCES = Path("epg_sources.json")

def attr(line, key):
    m = re.search(rf'{key}="([^"]*)"', line)
    return m.group(1).strip() if m else ""

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

wanted = {}
channel_rows = []

for line in PLAYLIST.read_text(errors="ignore").splitlines():
    if not line.startswith("#EXTINF"):
        continue
    tvg_id = attr(line, "tvg-id")
    logo = attr(line, "tvg-logo")
    name = line.split(",", 1)[-1].strip()
    if not tvg_id:
        tvg_id = re.sub(r"[^A-Za-z0-9]+", ".", name).strip(".") + ".branden"
    wanted[tvg_id] = name
    wanted[norm(name)] = name
    channel_rows.append((tvg_id, name, logo))

out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="BrandenTV">']
programmes = []
matched_ids = set()

for source, url in json.load(open(SOURCES)).items():
    print("Downloading EPG", source)
    try:
        data = urllib.request.urlopen(url, timeout=30).read()
        if url.endswith(".gz"):
            data = gzip.decompress(data)
        root = ET.fromstring(data)

        source_channels = {}
        for ch in root.findall("channel"):
            cid = ch.attrib.get("id", "")
            names = [x.text or "" for x in ch.findall("display-name")]
            keys = [cid] + [norm(n) for n in names]
            for k in keys:
                if k in wanted:
                    source_channels[cid] = wanted[k]
                    matched_ids.add(k)

        for prog in root.findall("programme"):
            cid = prog.attrib.get("channel", "")
            if cid in source_channels:
                programmes.append(ET.tostring(prog, encoding="unicode"))

        print("  matched channels:", len(source_channels), "programmes:", len(programmes))
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
