#!/usr/bin/env python3

import json
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path("docs/BrandenTV.xml")
EXTRACT = Path("docs/iptv-epg-missing-approved.xml")
MAPPING = Path("docs/iptv-epg-missing-approved-map.json")
REPORT = Path("docs/iptv-epg-exact-merge-report.txt")

if not BASE.exists():
    raise SystemExit(f"Missing base EPG: {BASE}")

if not EXTRACT.exists():
    raise SystemExit(f"Missing exact extract: {EXTRACT}")

if not MAPPING.exists():
    raise SystemExit(f"Missing mapping file: {MAPPING}")

mapping = json.loads(MAPPING.read_text())

# source-id -> BrandenTV tvg-id
source_to_branden = {
    info["source_id"]: info["branden_tvg_id"]
    for info in mapping.values()
}

base_root = ET.parse(BASE).getroot()
extract_root = ET.parse(EXTRACT).getroot()

# Prevent duplicate programmes when this script is run repeatedly.
existing_keys = set()

for programme in base_root.findall("programme"):
    title_node = programme.find("title")
    title = (title_node.text or "").strip() if title_node is not None else ""

    existing_keys.add((
        programme.attrib.get("channel", ""),
        programme.attrib.get("start", ""),
        programme.attrib.get("stop", ""),
        title,
    ))

added_by_channel = {}
duplicates = 0
unmapped = 0

for programme in extract_root.findall("programme"):
    source_id = programme.attrib.get("channel", "")
    branden_id = source_to_branden.get(source_id)

    if not branden_id:
        unmapped += 1
        continue

    title_node = programme.find("title")
    title = (title_node.text or "").strip() if title_node is not None else ""

    key = (
        branden_id,
        programme.attrib.get("start", ""),
        programme.attrib.get("stop", ""),
        title,
    )

    if key in existing_keys:
        duplicates += 1
        continue

    programme.attrib["channel"] = branden_id
    base_root.append(programme)
    existing_keys.add(key)

    added_by_channel[branden_id] = added_by_channel.get(branden_id, 0) + 1

ET.indent(base_root, space="  ")
ET.ElementTree(base_root).write(
    BASE,
    encoding="utf-8",
    xml_declaration=True,
)

lines = [
    "BrandenTV Exact IPTV-EPG Merge",
    "=" * 76,
    f"Approved mappings: {len(mapping)}",
    f"Programmes added: {sum(added_by_channel.values())}",
    f"Duplicate programmes skipped: {duplicates}",
    f"Unmapped programmes skipped: {unmapped}",
    "",
]

for channel_id, count in sorted(added_by_channel.items()):
    lines.append(f"{channel_id} | added={count}")

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Updated:", BASE)
print("Programmes added:", sum(added_by_channel.values()))
print("Duplicates skipped:", duplicates)
print("Channels strengthened:", len(added_by_channel))
print("Report:", REPORT)
