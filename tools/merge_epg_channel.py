#!/usr/bin/env python3

import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path


def local_tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def count_programmes(path: Path) -> Counter:
    counts = Counter()

    for _, elem in ET.iterparse(path, events=("end",)):
        if local_tag(elem.tag) == "programme":
            channel_id = elem.attrib.get("channel", "")

            if channel_id:
                counts[channel_id] += 1

        elem.clear()

    return counts


def indent_top_level(xml_text: str) -> str:
    return "\n".join(
        "  " + line if line else line
        for line in xml_text.splitlines()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge exactly one extracted XMLTV channel into "
            "BrandenTV.xml without altering unrelated channels."
        )
    )

    parser.add_argument("--base", required=True)
    parser.add_argument("--extract", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--report", required=True)

    args = parser.parse_args()

    base = Path(args.base)
    extract = Path(args.extract)
    report = Path(args.report)

    source_id = args.source_id
    target_id = args.target_id
    target_name = args.target_name

    if not base.exists():
        raise SystemExit(f"Base EPG not found: {base}")

    if not extract.exists():
        raise SystemExit(f"Extract not found: {extract}")

    report.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path("docs/backups") / (
        f"{base.name}.{target_id}.{timestamp}.bak"
    )
    temp = base.with_name(base.name + ".one-channel-new")

    backup.parent.mkdir(parents=True, exist_ok=True)

    extract_root = ET.parse(extract).getroot()

    source_channel = None
    source_programmes = []

    for elem in extract_root:
        kind = local_tag(elem.tag)

        if kind == "channel" and elem.attrib.get("id") == source_id:
            source_channel = elem

        elif (
            kind == "programme"
            and elem.attrib.get("channel") == source_id
        ):
            source_programmes.append(elem)

    if source_channel is None:
        raise SystemExit(
            f"Source channel node missing from extract: {source_id}"
        )

    if not source_programmes:
        raise SystemExit(
            f"No programmes found in extract for: {source_id}"
        )

    source_channel.attrib["id"] = target_id

    display_name_found = False

    for child in source_channel:
        if local_tag(child.tag) == "display-name":
            child.text = target_name
            display_name_found = True
            break

    if not display_name_found:
        display_name = ET.Element("display-name")
        display_name.text = target_name
        source_channel.insert(0, display_name)

    for programme in source_programmes:
        programme.attrib["channel"] = target_id

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

    before_counts = count_programmes(base)
    shutil.copy2(base, backup)

    lines = base.read_text(encoding="utf-8").splitlines()

    output = []
    index = 0

    inserted_channel = False
    inserted_programmes = False
    removed_channel_nodes = 0
    removed_programmes = 0

    while index < len(lines):
        line = lines[index]

        if re.match(r"^\s*<channel\b", line):
            block = [line]
            index += 1

            while index < len(lines):
                block.append(lines[index])

                if "</channel>" in lines[index]:
                    index += 1
                    break

                index += 1

            if f'id="{target_id}"' in block[0]:
                removed_channel_nodes += 1
                continue

            output.extend(block)
            continue

        if re.match(r"^\s*<programme\b", line):
            if not inserted_channel:
                output.append(channel_block)
                inserted_channel = True

            block = [line]
            index += 1

            while index < len(lines):
                block.append(lines[index])

                if "</programme>" in lines[index]:
                    index += 1
                    break

                index += 1

            if f'channel="{target_id}"' in block[0]:
                removed_programmes += 1
                continue

            output.extend(block)
            continue

        if line.strip() == "</tv>" and not inserted_programmes:
            if not inserted_channel:
                output.append(channel_block)
                inserted_channel = True

            output.extend(programme_blocks)
            inserted_programmes = True

        output.append(line)
        index += 1

    if not inserted_programmes:
        temp.unlink(missing_ok=True)
        raise SystemExit("Could not find closing </tv> element")

    temp.write_text(
        "\n".join(output) + "\n",
        encoding="utf-8",
    )

    # Confirm the output remains valid XML.
    ET.parse(temp)

    after_counts = count_programmes(temp)

    changed_others = []

    for channel_id in sorted(set(before_counts) | set(after_counts)):
        if channel_id == target_id:
            continue

        before = before_counts.get(channel_id, 0)
        after = after_counts.get(channel_id, 0)

        if before != after:
            changed_others.append(
                (channel_id, before, after)
            )

    if changed_others:
        temp.unlink(missing_ok=True)

        print("SAFETY CHECK FAILED")
        print("Unrelated programme counts changed:")

        for channel_id, before, after in changed_others:
            print(
                f"  {channel_id}: {before} -> {after}"
            )

        raise SystemExit(1)

    target_count = after_counts.get(target_id, 0)

    if target_count != len(programme_blocks):
        temp.unlink(missing_ok=True)

        raise SystemExit(
            "Target programme count mismatch: "
            f"expected {len(programme_blocks)}, "
            f"found {target_count}"
        )

    temp.replace(base)

    report.write_text(
        "\n".join([
            "BrandenTV isolated one-channel EPG merge",
            "=" * 72,
            f"Source ID: {source_id}",
            f"Target ID: {target_id}",
            f"Target name: {target_name}",
            f"Programmes installed: {target_count}",
            (
                "Previous target programmes removed: "
                f"{removed_programmes}"
            ),
            (
                "Previous target channel nodes removed: "
                f"{removed_channel_nodes}"
            ),
            "Unrelated programme counts changed: 0",
            f"Backup: {backup}",
        ]) + "\n",
        encoding="utf-8",
    )

    print("Updated:", base)
    print("Target:", target_name)
    print("Programmes installed:", target_count)
    print("Unrelated channels changed: 0")
    print("Backup:", backup)
    print("Report:", report)


if __name__ == "__main__":
    main()
