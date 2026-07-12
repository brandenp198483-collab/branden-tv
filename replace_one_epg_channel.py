#!/usr/bin/env python3

import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

BASE = Path("docs/BrandenTV.xml")
SOURCE = Path("docs/ABC-KATU-Test.xml")
BACKUP = Path("docs/BrandenTV.xml.before-abc-katu")
TEMP = Path("docs/BrandenTV.xml.abc-katu-new")
REPORT = Path("docs/abc-katu-isolated-merge-report.txt")

TARGET_ID = "ABC.branden"
SOURCE_ID = "ABCKATU.us"

def count_programmes(path):
    counts = Counter()

    for _, elem in ET.iterparse(path, events=("end",)):
        tag = elem.tag.rsplit("}", 1)[-1]

        if tag == "programme":
            channel = elem.attrib.get("channel", "")
            counts[channel] += 1

        elem.clear()

    return counts

def get_source_programme_blocks():
    root = ET.parse(SOURCE).getroot()
    blocks = []

    for programme in root.findall("programme"):
        if programme.attrib.get("channel") != SOURCE_ID:
            continue

        programme.attrib["channel"] = TARGET_ID
        ET.indent(programme, space="  ")

        text = ET.tostring(
            programme,
            encoding="unicode",
            short_empty_elements=True,
        )

        # Match the existing document's two-space top-level indentation.
        indented = "\n".join(
            "  " + line if line else line
            for line in text.splitlines()
        )

        blocks.append(indented)

    return blocks

if not BASE.exists():
    raise SystemExit(f"Missing base EPG: {BASE}")

if not SOURCE.exists():
    raise SystemExit(f"Missing isolated source: {SOURCE}")

before_counts = count_programmes(BASE)
source_blocks = get_source_programme_blocks()

if not source_blocks:
    raise SystemExit("No KATU programme blocks found")

shutil.copy2(BASE, BACKUP)

lines = BASE.read_text(errors="strict").splitlines()

output = []
i = 0
removed = 0
inserted = False

programme_start = re.compile(r"^\s*<programme\b")
target_channel = re.compile(
    rf'\bchannel="{re.escape(TARGET_ID)}"'
)

while i < len(lines):
    line = lines[i]

    if programme_start.search(line):
        block = [line]
        i += 1

        while i < len(lines):
            block.append(lines[i])

            if "</programme>" in lines[i]:
                i += 1
                break

            i += 1

        opening = block[0]

        if target_channel.search(opening):
            removed += 1
            continue

        output.extend(block)
        continue

    if line.strip() == "</tv>" and not inserted:
        output.extend(source_blocks)
        inserted = True

    output.append(line)
    i += 1

if not inserted:
    raise SystemExit("Could not find closing </tv> tag")

TEMP.write_text("\n".join(output) + "\n", encoding="utf-8")

# Confirm the rewritten file is valid XML.
ET.parse(TEMP)

after_counts = count_programmes(TEMP)

# Every channel except ABC must have exactly the same programme count.
all_ids = set(before_counts) | set(after_counts)
changed_others = []

for channel_id in sorted(all_ids):
    if channel_id == TARGET_ID:
        continue

    before = before_counts.get(channel_id, 0)
    after = after_counts.get(channel_id, 0)

    if before != after:
        changed_others.append((channel_id, before, after))

if changed_others:
    TEMP.unlink(missing_ok=True)

    print("SAFETY CHECK FAILED")
    print("Unrelated channels changed:")

    for channel_id, before, after in changed_others:
        print(channel_id, before, "->", after)

    raise SystemExit(1)

old_abc = before_counts.get(TARGET_ID, 0)
new_abc = after_counts.get(TARGET_ID, 0)

if new_abc != len(source_blocks):
    TEMP.unlink(missing_ok=True)
    raise SystemExit(
        f"ABC count mismatch: expected {len(source_blocks)}, got {new_abc}"
    )

TEMP.replace(BASE)

REPORT.write_text(
    "\n".join([
        "ABC KATU isolated EPG replacement",
        "=" * 72,
        f"Target ID: {TARGET_ID}",
        f"Source ID: {SOURCE_ID}",
        f"Old ABC programmes removed: {removed}",
        f"Old ABC programme count: {old_abc}",
        f"New KATU programmes inserted: {new_abc}",
        "Unrelated programme counts changed: 0",
        f"Backup: {BACKUP}",
    ]) + "\n",
    encoding="utf-8",
)

print("Updated:", BASE)
print("Old ABC programmes:", old_abc)
print("New ABC programmes:", new_abc)
print("Unrelated channels changed: 0")
print("Backup:", BACKUP)
print("Report:", REPORT)
