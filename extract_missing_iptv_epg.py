#!/usr/bin/env python3

import gzip
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("docs/iptv-epg-pfcutlblfg.xml.gz")
IDENTITY = Path("epg_identity.json")
MISSING_REPORT = Path("docs/epg-missing-report.txt")

OUT_XML = Path("docs/iptv-epg-missing-approved.xml")
OUT_GZ = Path("docs/iptv-epg-missing-approved.xml.gz")
REPORT = Path("docs/iptv-epg-missing-approved-report.txt")
MAPPING_JSON = Path("docs/iptv-epg-missing-approved-map.json")

def tag_name(tag):
    return tag.rsplit("}", 1)[-1]

def norm(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

def clean_source_name(value):
    value = re.sub(r"^\s*US\s*-\s*", "", value or "", flags=re.I)
    return value.strip()

identity = json.loads(IDENTITY.read_text())
identity_channels = identity.get("channels", {})

missing = []

for line in MISSING_REPORT.read_text(errors="ignore").splitlines():
    if not line.startswith("NO PROGRAMMES"):
        continue

    parts = [part.strip() for part in line.split("|")]

    if len(parts) >= 3:
        missing.append({
            "name": parts[1],
            "tvg_id": parts[2],
        })

targets = {}

for item in missing:
    name = item["name"]
    info = identity_channels.get(name, {})

    aliases = {name}
    aliases.update(info.get("aliases", []))

    station = info.get("station")
    if station:
        aliases.update({
            station,
            station + "-DT",
            station + "TV",
        })

    targets[name] = {
        "tvg_id": item["tvg_id"],
        "aliases": sorted(x for x in aliases if x),
        "norms": {norm(x) for x in aliases if norm(x)},
        "feed": info.get("feed", "east").lower(),
    }

# Explicit mappings for names that commonly differ.
# These still match exact source IDs, never fuzzy programme feeds.
EXPLICIT_IDS = {
    "E!": ["EEntertainmentTelevision.us"],
    "FX": ["FX.us"],

    "CNBC": ["CNBC.us"],
    "Fox Business Network": ["FoxBusiness.us"],
    "Fox News Channel": ["FoxNewsChannel.us"],
    "CBS Sports Network": ["CBSSportsNetwork.us"],
    "ESPNews": ["ESPNEWS.us"],
    "ESPNU": ["ESPNU.us"],
    "HGTV": ["HGTV.us"],
    "Heroes & Icons": ["HeroesAndIconsNetwork.us"],
    "Classic Arts Showcase": ["ClassicArtsShowcase.us"],
    "Investigation Discovery": [
        "InvestigationDiscovery.us",
        "IDDiscovery.us",
    ],
    "Science Channel": [
        "ScienceChannel.us",
        "DiscoveryScience.us",
    ],
    "Discovery Turbo": ["DiscoveryTurbo.us"],
    "MGM+": ["MGM+.us"],
    "MGM+ Drive-In": ["MGM+DriveIn.us"],
    "MGM+ Hits": ["MGM+Hits.us"],
    "MGM+ Marquee": ["MGM+Marquee.us"],

    "FX Movie Channel": ["FXMovies.us"],
    "Vice TV": ["Vice.us"],
    "MGM Westerns": ["MGMPresentsWesterns.us"],
    "ABC Tampa": ["ABCWFTS.us"],
    "FOX Tampa": ["FOXWTVT.us"],
    "NBC Boston": ["NBCWBTS.us"],
    "FOX Boston": ["FOXWFXT.us"],
    "NBC Philadelphia": ["NBCWCAU.us"],
    "FOX Philadelphia": ["FOXWTXF.us"],
}

source_channels = {}
candidate_matches = {name: [] for name in targets}

print("Pass 1: scanning U.S. channel identities...")

with gzip.open(SOURCE, "rb") as handle:
    for event, elem in ET.iterparse(handle, events=("end",)):
        tag = tag_name(elem.tag)

        if tag == "programme":
            break

        if tag != "channel":
            continue

        cid = elem.attrib.get("id", "").strip()

        display_names = [
            (child.text or "").strip()
            for child in elem
            if tag_name(child.tag) == "display-name"
            and (child.text or "").strip()
        ]

        is_us = (
            cid.lower().endswith(".us")
            or any(name.lower().startswith("us -") for name in display_names)
        )

        if not is_us:
            elem.clear()
            continue

        source_channels[cid] = {
            "id": cid,
            "names": display_names,
            "xml": ET.tostring(elem, encoding="unicode"),
        }

        cleaned_names = {
            norm(clean_source_name(name))
            for name in display_names
            if norm(clean_source_name(name))
        }

        id_norm = norm(re.sub(r"\.us$", "", cid, flags=re.I))

        for wanted, info in targets.items():
            score = 0
            reason = ""

            if cid in EXPLICIT_IDS.get(wanted, []):
                score = 1000
                reason = "explicit-id"

            if score == 0 and id_norm in info["norms"]:
                score = 900
                reason = "exact-id"

            if score == 0:
                exact_names = cleaned_names & info["norms"]

                if exact_names:
                    score = 800
                    reason = "exact-display-name"

            if score == 0:
                continue

            lower_combined = " ".join([cid, *display_names]).lower()

            # Prevent East channels from receiving West/Pacific schedules.
            if info["feed"] != "west":
                is_west_feed = (
                    re.search(r"\bwest\b", lower_combined) is not None
                    or re.search(r"\bpacific\b", lower_combined) is not None
                )

                if is_west_feed:
                    continue

            candidate_matches[wanted].append({
                "score": score,
                "reason": reason,
                "id": cid,
                "names": display_names,
            })

        elem.clear()

approved = {}
ambiguous = {}
unmatched = []

for wanted, candidates in candidate_matches.items():
    candidates.sort(key=lambda x: (-x["score"], x["id"]))

    if not candidates:
        unmatched.append(wanted)
        continue

    best_score = candidates[0]["score"]
    best = [item for item in candidates if item["score"] == best_score]

    if len(best) == 1:
        approved[wanted] = best[0]
    else:
        ambiguous[wanted] = best

print("Approved exact mappings:", len(approved))
print("Ambiguous mappings:", len(ambiguous))
print("Unmatched:", len(unmatched))

approved_ids = {
    item["id"]: wanted
    for wanted, item in approved.items()
}

programme_counts = {
    cid: 0
    for cid in approved_ids
}

programme_xml = []

print("Pass 2: extracting approved programmes...")

with gzip.open(SOURCE, "rb") as handle:
    for event, elem in ET.iterparse(handle, events=("end",)):
        if tag_name(elem.tag) != "programme":
            elem.clear()
            continue

        cid = elem.attrib.get("channel", "")

        if cid in approved_ids:
            programme_xml.append(
                ET.tostring(elem, encoding="unicode")
            )
            programme_counts[cid] += 1

        elem.clear()

out = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<tv generator-info-name="BrandenTV exact missing-channel extract">',
]

for wanted in sorted(approved):
    cid = approved[wanted]["id"]
    out.append(source_channels[cid]["xml"])

out.extend(programme_xml)
out.append("</tv>")

xml_text = "\n".join(out) + "\n"

OUT_XML.write_text(xml_text, encoding="utf-8")

with gzip.open(OUT_GZ, "wb", compresslevel=9) as handle:
    handle.write(xml_text.encode("utf-8"))

mapping_output = {
    wanted: {
        "branden_tvg_id": targets[wanted]["tvg_id"],
        "source_id": item["id"],
        "source_names": item["names"],
        "reason": item["reason"],
        "programmes": programme_counts.get(item["id"], 0),
    }
    for wanted, item in approved.items()
}

MAPPING_JSON.write_text(
    json.dumps(mapping_output, indent=2) + "\n",
    encoding="utf-8",
)

lines = [
    "IPTV-EPG.org Exact Missing-Channel Extraction",
    "=" * 78,
    f"Missing BrandenTV channels examined: {len(targets)}",
    f"Exact approved mappings: {len(approved)}",
    f"Ambiguous mappings withheld: {len(ambiguous)}",
    f"Unmatched channels: {len(unmatched)}",
    f"Programmes extracted: {sum(programme_counts.values())}",
    "",
    "APPROVED",
    "=" * 78,
]

for wanted in sorted(approved):
    item = approved[wanted]
    count = programme_counts.get(item["id"], 0)

    lines.extend([
        f"{wanted} | {targets[wanted]['tvg_id']}",
        f"  source-id: {item['id']}",
        f"  reason:    {item['reason']}",
        f"  programmes:{count}",
    ])

    for source_name in item["names"]:
        lines.append(f"  name:      {source_name}")

    lines.append("")

lines.extend([
    "AMBIGUOUS — NOT EXTRACTED",
    "=" * 78,
])

for wanted in sorted(ambiguous):
    lines.append(wanted)

    for item in ambiguous[wanted]:
        lines.append(
            f"  {item['id']} | score={item['score']} | "
            f"{', '.join(item['names'])}"
        )

    lines.append("")

lines.extend([
    "UNMATCHED",
    "=" * 78,
])

lines.extend(sorted(unmatched) or ["None"])

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("XML:", OUT_XML)
print("GZIP:", OUT_GZ)
print("Mapping:", MAPPING_JSON)
print("Report:", REPORT)
print("Programmes:", sum(programme_counts.values()))
