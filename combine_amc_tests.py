#!/usr/bin/env python3

import re
from pathlib import Path
from urllib.parse import urlparse

OUT = Path("docs/BrandenTV-AMC-East-West-Test.m3u")
REPORT = Path("docs/amc-east-west-test-report.txt")

WANTED = re.compile(
    r"\bAMC\b.*\b(East|Eastern|West|Pacific)\b|"
    r"\b(East|Eastern|West|Pacific)\b.*\bAMC\b|"
    r"\bAMC\s+HD\b",
    re.I,
)

REJECT = re.compile(
    r"AMC\+|AMC Plus|AMC en espa|AMC Latino|"
    r"Walking Dead|Fear the Walking Dead|"
    r"IFC|Sundance|Asian|India|UK|Europe",
    re.I,
)

def credentialed(url: str) -> bool:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]

    # Common Xtream pattern: /live/username/password/channel
    return (
        len(parts) >= 4
        and parts[0].lower() == "live"
    ) or "@" in parsed.path

sources = sorted(
    Path("docs").glob("BrandenTV-GitHub-amc*-Test.m3u")
)

entries = []
seen_urls = set()

for path in sources:
    lines = path.read_text(errors="ignore").splitlines()

    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF") or "," not in line:
            continue

        name = line.rsplit(",", 1)[-1].strip()

        if not WANTED.search(name) or REJECT.search(name):
            continue

        if index + 1 >= len(lines):
            continue

        url = lines[index + 1].strip()

        if not url.startswith(("http://", "https://")):
            continue

        if url in seen_urls or credentialed(url):
            continue

        seen_urls.add(url)

        lower = name.lower()
        score = 0

        if "amc east" in lower:
            score += 120
        elif "eastern" in lower:
            score += 110
        elif "amc west" in lower:
            score += 90
        elif "pacific" in lower:
            score += 80

        if "1080" in lower or "fhd" in lower:
            score += 25
        elif "720" in lower or "hd" in lower:
            score += 15

        if url.startswith("https://"):
            score += 10

        entries.append({
            "name": name,
            "url": url,
            "source": str(path),
            "score": score,
        })

entries.sort(
    key=lambda item: (
        -item["score"],
        item["name"].lower(),
    )
)

playlist = ["#EXTM3U"]
report = [
    "AMC East/West isolated candidate test",
    "=" * 82,
    f"Source test playlists examined: {len(sources)}",
    f"Unique filtered candidates: {len(entries)}",
    "",
]

for number, item in enumerate(entries, 1):
    safe_name = item["name"].replace(",", " ")

    playlist.extend([
        (
            '#EXTINF:-1 group-title="AMC East-West Test",'
            f'{number:03d} - {safe_name} [score {item["score"]}]'
        ),
        item["url"],
    ])

    report.extend([
        "=" * 82,
        f'{number:03d}. {item["name"]}',
        f'Score: {item["score"]}',
        f'Source: {item["source"]}',
        f'URL: {item["url"]}',
        "",
    ])

OUT.write_text("\n".join(playlist) + "\n", encoding="utf-8")
REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

print("Source playlists examined:", len(sources))
print("Unique filtered candidates:", len(entries))
print("Playlist:", OUT)
print("Report:", REPORT)
