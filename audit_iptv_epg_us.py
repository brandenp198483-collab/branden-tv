#!/usr/bin/env python3

import gzip
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("docs/iptv-epg-pfcutlblfg.xml.gz")
IDENTITY = Path("epg_identity.json")
MISSING = Path("docs/epg-missing-report.txt")
REPORT = Path("docs/iptv-epg-us-channel-audit.txt")
JSON_OUT = Path("docs/iptv-epg-us-channel-candidates.json")

def local_tag(tag):
    return tag.rsplit("}", 1)[-1]

def norm(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

def words(value):
    return set(re.findall(r"[a-z0-9]+", (value or "").lower()))

identity = json.loads(IDENTITY.read_text())
identity_channels = identity.get("channels", {})

missing_names = []

for line in MISSING.read_text(errors="ignore").splitlines():
    if line.startswith("NO PROGRAMMES"):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 3:
            missing_names.append(parts[1])

targets = {}

for name in missing_names:
    info = identity_channels.get(name, {})

    aliases = {name}
    aliases.update(info.get("aliases", []))

    station = info.get("station")
    if station:
        aliases.add(station)

    targets[name] = {
        "aliases": sorted(aliases),
        "norms": {norm(x) for x in aliases if norm(x)},
        "words": words(" ".join(aliases)),
    }

results = {name: [] for name in targets}
us_channels_seen = 0
all_channels_seen = 0

print("Streaming channel section...")

with gzip.open(SOURCE, "rb") as handle:
    for event, elem in ET.iterparse(handle, events=("end",)):
        tag = local_tag(elem.tag)

        if tag == "programme":
            # XMLTV normally lists every channel before programmes.
            break

        if tag != "channel":
            continue

        all_channels_seen += 1

        cid = elem.attrib.get("id", "").strip()
        display_names = [
            (node.text or "").strip()
            for node in elem
            if local_tag(node.tag) == "display-name"
            and (node.text or "").strip()
        ]

        combined = " ".join([cid, *display_names])
        combined_norm = norm(combined)
        combined_words = words(combined)

        # Keep U.S. guide entries only.
        is_us = (
            cid.lower().endswith(".us")
            or any(name.lower().startswith("us -") for name in display_names)
            or "united states" in combined.lower()
        )

        if not is_us:
            elem.clear()
            continue

        us_channels_seen += 1

        for wanted, info in targets.items():
            score = 0

            for alias_norm in info["norms"]:
                if not alias_norm:
                    continue

                if alias_norm == norm(cid):
                    score = max(score, 300)

                for display_name in display_names:
                    display_norm = norm(display_name)

                    if alias_norm == display_norm:
                        score = max(score, 280)
                    elif alias_norm in display_norm:
                        score = max(score, 180)
                    elif display_norm and display_norm in alias_norm:
                        score = max(score, 140)

            overlap = len(info["words"] & combined_words)

            if overlap:
                score = max(score, overlap * 45)

            if score > 0:
                results[wanted].append({
                    "score": score,
                    "id": cid,
                    "display_names": display_names,
                })

        elem.clear()

for wanted in results:
    unique = {}

    for item in results[wanted]:
        key = item["id"]

        if key not in unique or item["score"] > unique[key]["score"]:
            unique[key] = item

    results[wanted] = sorted(
        unique.values(),
        key=lambda item: (-item["score"], item["id"].lower()),
    )[:20]

lines = [
    "IPTV-EPG.org U.S. Channel Audit",
    "=" * 78,
    f"All channel records examined: {all_channels_seen}",
    f"U.S. channel records examined: {us_channels_seen}",
    f"Missing BrandenTV targets: {len(targets)}",
    "",
]

matched_targets = 0

for wanted in sorted(results):
    candidates = results[wanted]

    lines.extend([
        "=" * 78,
        wanted,
        f'Current aliases: {", ".join(targets[wanted]["aliases"])}',
        "",
    ])

    if not candidates:
        lines.append("NO U.S. CANDIDATES")
        lines.append("")
        continue

    matched_targets += 1

    for number, item in enumerate(candidates, 1):
        lines.append(
            f'{number:02d}. score={item["score"]} | id={item["id"]}'
        )

        for display_name in item["display_names"]:
            lines.append(f"    name={display_name}")

    lines.append("")

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
JSON_OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

print("All channels examined:", all_channels_seen)
print("U.S. channels examined:", us_channels_seen)
print("Targets with candidates:", matched_targets)
print("Report:", REPORT)
print("JSON:", JSON_OUT)
