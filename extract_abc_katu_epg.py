#!/usr/bin/env python3

import copy
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("docs/iptv-epg-pfcutlblfg.xml.gz")
OUT = Path("docs/ABC-KATU-Test.xml")
REPORT = Path("docs/ABC-KATU-Test-report.txt")

SOURCE_ID = "ABCKATU.us"

channel_element = None
programmes = []

with gzip.open(SOURCE, "rb") as handle:
    for _, elem in ET.iterparse(handle, events=("end",)):
        tag = elem.tag.rsplit("}", 1)[-1]

        if tag == "channel":
            if elem.attrib.get("id") == SOURCE_ID:
                channel_element = copy.deepcopy(elem)

            # Safe to clear only after the complete channel was examined.
            elem.clear()

        elif tag == "programme":
            if elem.attrib.get("channel") == SOURCE_ID:
                programmes.append(copy.deepcopy(elem))

            # Safe to clear only after the complete programme was examined.
            elem.clear()

        # IMPORTANT:
        # Do not clear title, desc, category, episode-num, etc.
        # They must remain attached until their parent programme ends.

if channel_element is None:
    raise SystemExit(f"Source channel not found: {SOURCE_ID}")

if not programmes:
    raise SystemExit(f"No programmes found for: {SOURCE_ID}")

root = ET.Element(
    "tv",
    {"generator-info-name": "BrandenTV isolated ABC KATU test"},
)

root.append(channel_element)

for programme in programmes:
    root.append(programme)

ET.indent(root, space="  ")

ET.ElementTree(root).write(
    OUT,
    encoding="utf-8",
    xml_declaration=True,
)

titles = []

for programme in programmes[:30]:
    title_text = ""

    for child in programme:
        if child.tag.rsplit("}", 1)[-1] == "title":
            title_text = (child.text or "").strip()
            break

    titles.append(title_text or "[NO TITLE]")

REPORT.write_text(
    "\n".join([
        "ABC KATU isolated EPG extract",
        "=" * 72,
        f"Source ID: {SOURCE_ID}",
        f"Programmes: {len(programmes)}",
        f"Titles found in sample: "
        f"{sum(title != '[NO TITLE]' for title in titles)} of {len(titles)}",
        "",
        "First programme titles:",
        *[f"- {title}" for title in titles],
    ]) + "\n",
    encoding="utf-8",
)

print("Created:", OUT)
print("Programmes:", len(programmes))
print(
    "Titles found in sample:",
    sum(title != "[NO TITLE]" for title in titles),
    "of",
    len(titles),
)
print("Report:", REPORT)
