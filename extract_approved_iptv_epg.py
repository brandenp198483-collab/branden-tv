#!/usr/bin/env python3

import gzip
import html
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("docs/iptv-epg-pfcutlblfg.xml.gz")
OUT_XML = Path("docs/iptv-epg-us-approved.xml")
OUT_GZ = Path("docs/iptv-epg-us-approved.xml.gz")
REPORT = Path("docs/iptv-epg-us-approved-report.txt")

# Exact source display names only—no fuzzy matching.
APPROVED = {
    "US - MGM+",
    "US - MGM+ West",
    "US - MGM+ Hits",
    "US - MGM+ Marquee",
    "US - MGM+ Drive-In",
    "US - MGM Presents: Westerns",

    "US - CNBC",
    "US - ESPNEWS",
    "US - ESPN U",
    "US - Fox Business",
    "US - FOX NEWS",
    "US - HGTV",
    "US - HEROES & ICONS",
    "US - CBS SPORTS NETWORK",
    "US - Classic Arts Showcase",

    "US - Investigation Discovery",
    "US - Science Channel",
    "US - Discovery Turbo",
    "US - FX",
    "US - FXM",
    "US - E!",
}

def tag_name(tag):
    return tag.rsplit("}", 1)[-1]

approved_ids = {}
channel_xml = {}

print("Pass 1: finding exact approved channels...")

with gzip.open(SOURCE, "rb") as handle:
    for event, elem in ET.iterparse(handle, events=("end",)):
        tag = tag_name(elem.tag)

        if tag == "programme":
            break

        if tag != "channel":
            continue

        cid = elem.attrib.get("id", "").strip()
        names = [
            (child.text or "").strip()
            for child in elem
            if tag_name(child.tag) == "display-name"
            and (child.text or "").strip()
        ]

        matched_names = sorted(set(names) & APPROVED)

        if matched_names:
            approved_ids[cid] = matched_names[0]
            channel_xml[cid] = ET.tostring(
                elem,
                encoding="unicode",
            )

        elem.clear()

print("Approved source IDs found:", len(approved_ids))

for cid, name in sorted(approved_ids.items(), key=lambda x: x[1]):
    print(f"  {name} -> {cid}")

programmes = []
programme_counts = {cid: 0 for cid in approved_ids}

print("Pass 2: extracting programmes—this may take a few minutes...")

with gzip.open(SOURCE, "rb") as handle:
    for event, elem in ET.iterparse(handle, events=("end",)):
        if tag_name(elem.tag) != "programme":
            elem.clear()
            continue

        cid = elem.attrib.get("channel", "")

        if cid in approved_ids:
            programmes.append(
                ET.tostring(elem, encoding="unicode")
            )
            programme_counts[cid] += 1

        elem.clear()

out = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<tv generator-info-name="BrandenTV approved IPTV-EPG extract">',
]

for cid in sorted(channel_xml, key=lambda x: approved_ids[x]):
    out.append(channel_xml[cid])

out.extend(programmes)
out.append("</tv>")

xml_text = "\n".join(out) + "\n"
OUT_XML.write_text(xml_text, encoding="utf-8")

with gzip.open(OUT_GZ, "wb", compresslevel=9) as handle:
    handle.write(xml_text.encode("utf-8"))

report = [
    "BrandenTV Approved IPTV-EPG Extract",
    "=" * 76,
    f"Approved names requested: {len(APPROVED)}",
    f"Source channels found: {len(approved_ids)}",
    f"Programmes extracted: {sum(programme_counts.values())}",
    "",
]

for cid, source_name in sorted(
    approved_ids.items(),
    key=lambda item: item[1].lower(),
):
    report.append(
        f"{source_name} | {cid} | programmes={programme_counts[cid]}"
    )

missing = sorted(
    APPROVED - {
        name
        for names in approved_ids.values()
        for name in [names]
    }
)

report.extend([
    "",
    "NOT FOUND",
    "=" * 76,
])

report.extend(missing or ["None"])

REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

print("XML:", OUT_XML)
print("GZIP:", OUT_GZ)
print("Report:", REPORT)
print("Programmes:", sum(programme_counts.values()))
