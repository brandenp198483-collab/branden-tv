#!/usr/bin/env python3

import re
import xml.etree.ElementTree as ET
from pathlib import Path

PLAYLIST = Path("output/BrandenTV-Stremio.m3u")
EPG = Path("docs/BrandenTV.xml")
REPORT = Path("docs/epg-missing-report.txt")

def attr(line, key):
    match = re.search(rf'{re.escape(key)}="([^"]*)"', line)
    return match.group(1).strip() if match else ""

playlist_channels = []

for line in PLAYLIST.read_text(errors="ignore").splitlines():
    if not line.startswith("#EXTINF"):
        continue

    name = line.rsplit(",", 1)[-1].strip()
    tvg_id = attr(line, "tvg-id")

    playlist_channels.append({
        "name": name,
        "tvg_id": tvg_id,
    })

channel_ids = set()
programme_counts = {}

# Stream the XML so Termux does not need to hold the whole guide in memory.
for event, elem in ET.iterparse(EPG, events=("end",)):
    tag = elem.tag.rsplit("}", 1)[-1]

    if tag == "channel":
        cid = elem.attrib.get("id", "").strip()
        if cid:
            channel_ids.add(cid)

    elif tag == "programme":
        cid = elem.attrib.get("channel", "").strip()
        if cid:
            programme_counts[cid] = programme_counts.get(cid, 0) + 1

    elem.clear()

working = 0
no_programmes = 0
no_xml_channel = 0
no_tvg_id = 0

lines = []

for item in playlist_channels:
    name = item["name"]
    tvg_id = item["tvg_id"]

    if not tvg_id:
        status = "NO TVG-ID"
        no_tvg_id += 1

    elif tvg_id not in channel_ids:
        status = "NO XML CHANNEL"
        no_xml_channel += 1

    elif programme_counts.get(tvg_id, 0) == 0:
        status = "NO PROGRAMMES"
        no_programmes += 1

    else:
        status = "WORKING"
        working += 1

    lines.append(f"{status:<15} | {name} | {tvg_id}")

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Playlist channels:", len(playlist_channels))
print("EPG working:", working)
print("No programmes:", no_programmes)
print("No XML channel:", no_xml_channel)
print("No tvg-id:", no_tvg_id)
print("Report:", REPORT)
