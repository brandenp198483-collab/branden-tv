#!/usr/bin/env python3

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

EPG = Path("docs/BrandenTV.xml")
SOURCE = Path("docs/iptv-epg-pfcutlblfg.xml.gz")
REPORT = Path("docs/abc-katu-epg-replacement-report.txt")

TARGET_TVG = "ABC.branden"
SOURCE_ID = "ABCKATU.us"

root = ET.parse(EPG).getroot()

# Count and remove only the existing ABC.branden programmes.
removed = 0

for programme in list(root.findall("programme")):
    if programme.attrib.get("channel") == TARGET_TVG:
        root.remove(programme)
        removed += 1

# Extract only ABCKATU.us programmes from the large source.
added = 0

with gzip.open(SOURCE, "rb") as handle:
    for _, elem in ET.iterparse(handle, events=("end",)):
        tag = elem.tag.rsplit("}", 1)[-1]

        if tag != "programme":
            elem.clear()
            continue

        if elem.attrib.get("channel") == SOURCE_ID:
            elem.attrib["channel"] = TARGET_TVG
            root.append(elem)
            added += 1
        else:
            elem.clear()

ET.indent(root, space="  ")
ET.ElementTree(root).write(
    EPG,
    encoding="utf-8",
    xml_declaration=True,
)

REPORT.write_text(
    "\n".join([
        "ABC EPG isolated replacement",
        "=" * 72,
        f"Target: {TARGET_TVG}",
        f"Source: {SOURCE_ID}",
        f"Old ABC programmes removed: {removed}",
        f"KATU programmes added: {added}",
    ]) + "\n",
    encoding="utf-8",
)

print("Updated:", EPG)
print("Old ABC programmes removed:", removed)
print("KATU programmes added:", added)
print("Report:", REPORT)
