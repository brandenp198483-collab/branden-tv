#!/usr/bin/env python3

import re
from pathlib import Path

SEARCH_ROOTS = [
    Path("github_m3u_cache"),
    Path("docs/github-scans"),
    Path("docs"),
    Path("playlists"),
]

OUT = Path("docs/BrandenTV-WFTS-Tampa-Raw-Test.m3u")
REPORT = Path("docs/wfts-tampa-raw-test-report.txt")

WANTED = re.compile(
    r"\bWFTS\b|"
    r"ABC\s*(?:Action\s*News\s*)?Tampa|"
    r"Tampa\s*(?:Bay\s*)?ABC|"
    r"ABC\s*28\s*Tampa",
    re.I,
)

REJECT = re.compile(
    r"FOX|NBC|CBS|PBS|WFLA|WTVT|WTSP",
    re.I,
)

def find_url(lines, start):
    for line in lines[start + 1:start + 8]:
        value = line.strip()

        if value.startswith(("http://", "https://")):
            return value

        match = re.match(r"URL:\s*(https?://\S+)", value, re.I)
        if match:
            return match.group(1)

        if value.startswith("#EXTINF"):
            break

    return ""

candidates = []

for root in SEARCH_ROOTS:
    if not root.exists():
        continue

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in {
            ".m3u", ".m3u8", ".txt", ".json"
        }:
            continue

        try:
            lines = path.read_text(errors="ignore").splitlines()
        except Exception:
            continue

        for index, line in enumerate(lines):
            if not WANTED.search(line):
                continue

            if REJECT.search(line):
                continue

            url = find_url(lines, index)

            # Reports often place URL a few lines later.
            if not url:
                for nearby in lines[index:index + 12]:
                    match = re.search(r"https?://[^\s\"\\]+", nearby)
                    if match:
                        url = match.group(0).rstrip('",')
                        break

            if not url:
                continue

            label = line.strip()

            if line.startswith("#EXTINF") and "," in line:
                label = line.rsplit(",", 1)[-1].strip()

            candidates.append({
                "name": label,
                "url": url,
                "source": str(path),
            })

# Deduplicate by URL.
unique = {}

for item in candidates:
    unique.setdefault(item["url"], item)

items = list(unique.values())

# Exact WFTS labels first.
items.sort(
    key=lambda item: (
        0 if "wfts" in item["name"].lower() else 1,
        item["name"].lower(),
    )
)

test_lines = ["#EXTM3U"]
report_lines = [
    "Recovered WFTS Tampa candidates",
    "=" * 78,
    f"Unique candidates: {len(items)}",
    "",
]

for number, item in enumerate(items, 1):
    clean_name = item["name"].replace(",", " ")

    test_lines.extend([
        (
            '#EXTINF:-1 group-title="WFTS Tampa Raw Test",'
            f'{number:03d} - {clean_name}'
        ),
        item["url"],
    ])

    report_lines.extend([
        "=" * 78,
        f'{number:03d}. {item["name"]}',
        f'Source: {item["source"]}',
        f'URL: {item["url"]}',
        "",
    ])

OUT.write_text("\n".join(test_lines) + "\n", encoding="utf-8")
REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

print("Recovered candidates:", len(items))
print("Test playlist:", OUT)
print("Report:", REPORT)
