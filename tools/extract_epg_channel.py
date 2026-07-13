#!/usr/bin/env python3

import argparse
import copy
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path


def local_tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract exactly one XMLTV channel and its programmes."
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Source XML or XML.GZ file",
    )
    parser.add_argument(
        "--source-id",
        required=True,
        help="Exact XMLTV source channel ID",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output XML file",
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Output report file",
    )

    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    report = Path(args.report)
    source_id = args.source_id

    if not source.exists():
        raise SystemExit(f"Source file not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    opener = gzip.open if source.name.lower().endswith(".gz") else open

    channel_element = None
    programmes = []

    print(f"Extracting exact channel: {source_id}")

    with opener(source, "rb") as handle:
        for _, elem in ET.iterparse(handle, events=("end",)):
            kind = local_tag(elem.tag)

            if kind == "channel":
                if elem.attrib.get("id") == source_id:
                    channel_element = copy.deepcopy(elem)

                elem.clear()

            elif kind == "programme":
                if elem.attrib.get("channel") == source_id:
                    programmes.append(copy.deepcopy(elem))

                elem.clear()

            # Do not clear title, description or category children
            # before the complete parent programme is processed.

    if channel_element is None:
        raise SystemExit(f"Channel ID not found: {source_id}")

    if not programmes:
        raise SystemExit(f"No programmes found for: {source_id}")

    root = ET.Element(
        "tv",
        {
            "generator-info-name":
                "BrandenTV isolated one-channel EPG extract"
        },
    )

    root.append(channel_element)

    for programme in programmes:
        root.append(programme)

    ET.indent(root, space="  ")

    ET.ElementTree(root).write(
        output,
        encoding="utf-8",
        xml_declaration=True,
    )

    sample_titles = []

    for programme in programmes[:30]:
        title_text = ""

        for child in programme:
            if local_tag(child.tag) == "title":
                title_text = (child.text or "").strip()
                break

        sample_titles.append(title_text or "[NO TITLE]")

    titles_found = sum(
        title != "[NO TITLE]"
        for title in sample_titles
    )

    report.write_text(
        "\n".join([
            "BrandenTV isolated EPG extraction",
            "=" * 72,
            f"Source file: {source}",
            f"Source ID: {source_id}",
            f"Programmes extracted: {len(programmes)}",
            (
                "Titles found in sample: "
                f"{titles_found} of {len(sample_titles)}"
            ),
            "",
            "Sample titles:",
            *[f"- {title}" for title in sample_titles],
        ]) + "\n",
        encoding="utf-8",
    )

    print("Created:", output)
    print("Programmes:", len(programmes))
    print(
        "Titles found in sample:",
        titles_found,
        "of",
        len(sample_titles),
    )
    print("Report:", report)


if __name__ == "__main__":
    main()
