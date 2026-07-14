#!/usr/bin/env python3

import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

BASE = Path("docs/BrandenTV.xml")
SOURCE = Path("docs/Tampa-Bay-28-Plus-Test.xml")
BACKUP = Path("docs/BrandenTV.xml.before-tampa28-epg")
TEMP = Path("docs/BrandenTV.xml.tampa28-new")
REPORT = Path("docs/tampa-bay-28-plus-epg-merge-report.txt")

SOURCE_ID = "ABCWFTS.us"
TARGET_ID = "Tampa.Bay.28.Plus.branden"
TARGET_NAME = "Tampa Bay 28+"

def local_tag(value):
    return value.rsplit("}", 1)[-1]

def count_programmes(path):
    counts = Counter()

    for _, elem in ET.iterparse(path, events=("end",)):
        if local_tag(elem.tag) == "programme":
            cid = elem.attrib.get("channel", "")
            counts[cid] += 1

        elem.clear()

    return counts

def indent_top_level(xml_text):
    return "\n".join(
        "  " + line if line else line
        for line in xml_text.splitlines()
    )

source_root = ET.parse(SOURCE).getroot()

source_channel = None
source_programmes = []

for elem in source_root:
    kind = local_tag(elem.tag)

    if kind == "channel" and elem.attrib.get("id") == SOURCE_ID:
        source_channel = elem

    elif kind == "programme" and elem.attrib.get("channel") == SOURCE_ID:
        source_programmes.append(elem)

if source_channel is None:
    raise SystemExit("Source channel node not found")

if not source_programmes:
    raise SystemExit("Source programmes not found")

source_channel.attrib["id"] = TARGET_ID

for child in source_channel:
    if local_tag(child.tag) == "display-name":
        child.text = TARGET_NAME
        break

for programme in source_programmes:
    programme.attrib["channel"] = TARGET_ID

ET.indent(source_channel, space="  ")

channel_block = indent_top_level(
    ET.tostring(
        source_channel,
        encoding="unicode",
        short_empty_elements=True,
    )
)

programme_blocks = []

for programme in source_programmes:
    ET.indent(programme, space="  ")

    programme_blocks.append(
        indent_top_level(
            ET.tostring(
                programme,
                encoding="unicode",
                short_empty_elements=True,
            )
        )
    )

before_counts = count_programmes(BASE)
shutil.copy2(BASE, BACKUP)

lines = BASE.read_text(encoding="utf-8").splitlines()
output = []

i = 0
channel_inserted = False
programmes_inserted = False
removed_old_channels = 0
removed_old_programmes = 0

while i < len(lines):
    line = lines[i]

    if re.match(r"^\s*<channel\b", line):
        block = [line]
        i += 1

        while i < len(lines):
            block.append(lines[i])

            if "</channel>" in lines[i]:
                i += 1
                break

            i += 1

        if f'id="{TARGET_ID}"' in block[0]:
            removed_old_channels += 1
            continue

        output.extend(block)
        continue

    if re.match(r"^\s*<programme\b", line):
        if not channel_inserted:
            output.append(channel_block)
            channel_inserted = True

        block = [line]
        i += 1

        while i < len(lines):
            block.append(lines[i])

            if "</programme>" in lines[i]:
                i += 1
                break

            i += 1

        if f'channel="{TARGET_ID}"' in block[0]:
            removed_old_programmes += 1
            continue

        output.extend(block)
        continue

    if line.strip() == "</tv>" and not programmes_inserted:
        if not channel_inserted:
            output.append(channel_block)
            channel_inserted = True

        output.extend(programme_blocks)
        programmes_inserted = True

    output.append(line)
    i += 1

TEMP.write_text("\n".join(output) + "\n", encoding="utf-8")

# Must remain valid XML.
ET.parse(TEMP)

after_counts = count_programmes(TEMP)

changed_others = []

for cid in sorted(set(before_counts) | set(after_counts)):
    if cid == TARGET_ID:
        continue

    before = before_counts.get(cid, 0)
    after = after_counts.get(cid, 0)

    if before != after:
        changed_others.append((cid, before, after))

if changed_others:
    TEMP.unlink(missing_ok=True)

    print("SAFETY CHECK FAILED")

    for cid, before, after in changed_others:
        print(cid, before, "->", after)

    raise SystemExit(1)

target_count = after_counts.get(TARGET_ID, 0)

if target_count != len(programme_blocks):
    TEMP.unlink(missing_ok=True)
    raise SystemExit(
        f"Target count mismatch: expected {len(programme_blocks)}, "
        f"got {target_count}"
    )

TEMP.replace(BASE)

REPORT.write_text(
    "\n".join([
        "Tampa Bay 28+ isolated EPG merge",
        "=" * 72,
        f"Source ID: {SOURCE_ID}",
        f"Target ID: {TARGET_ID}",
        f"Programmes added: {target_count}",
        f"Previous target programmes removed: {removed_old_programmes}",
        f"Previous target channel nodes removed: {removed_old_channels}",
        "Unrelated programme counts changed: 0",
        f"Backup: {BACKUP}",
    ]) + "\n",
    encoding="utf-8",
)

print("Updated:", BASE)
print("Programmes added:", target_count)
print("Unrelated channels changed: 0")
print("Backup:", BACKUP)
print("Report:", REPORT)
