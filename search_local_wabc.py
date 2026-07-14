#!/usr/bin/env python3

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOTS = [
    Path("github_m3u_cache"),
    Path("scan_cache"),
    Path("playlists"),
]

REPORT = Path("docs/local-wabc-search-report.txt")
TEST = Path("docs/BrandenTV-Local-WABC-Test.m3u")
JSON_OUT = Path("docs/local-wabc-search-candidates.json")

TERMS = [
    "wabc",
    "wabc-tv",
    "wabc dt",
    "abc7 new york",
    "abc 7 new york",
    "abc new york",
    "new york abc",
    "ny new york abc",
    "abc east",
    "abc eastern",
]

REJECT = [
    "wnet",
    "pbs",
    "abc australia",
    "abc news live",
    "abc news",
    "abc radio",
    "abc kids",
]

def norm(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

def score_name(name):
    text = norm(name)

    if any(bad in text for bad in REJECT):
        return -999

    score = 0

    exact_boosts = {
        "wabc": 120,
        "wabc tv": 120,
        "abc7 new york": 115,
        "abc 7 new york": 115,
        "wabc new york": 115,
        "new york abc": 100,
        "ny new york abc": 100,
        "abc east": 70,
        "abc eastern": 70,
    }

    for term, points in exact_boosts.items():
        if term in text:
            score = max(score, points)

    if "new york" in text:
        score += 30

    if "abc" in text:
        score += 20

    if "hd" in text or "1080" in text or "720" in text:
        score += 10

    if "backup" in text:
        score -= 5

    return score

def parse_playlist(path):
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return []

    out = []

    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF") or "," not in line:
            continue

        name = line.rsplit(",", 1)[-1].strip()
        url = ""

        for candidate in lines[i + 1:i + 6]:
            candidate = candidate.strip()

            if candidate.startswith(("http://", "https://")):
                url = candidate
                break

            if candidate.startswith("#EXTINF"):
                break

        if not url:
            continue

        score = score_name(name)

        if score <= 0:
            continue

        out.append({
            "name": name,
            "url": url,
            "score": score,
            "source": str(path),
        })

    return out

files = []

for root in ROOTS:
    if not root.exists():
        continue

    files.extend(root.rglob("*.m3u"))
    files.extend(root.rglob("*.m3u8"))
    files.extend(root.rglob("*.txt"))

raw = []

for path in files:
    raw.extend(parse_playlist(path))

# Deduplicate by URL, keeping the highest-scoring label/source.
unique = {}

for item in raw:
    url = item["url"]

    if url not in unique or item["score"] > unique[url]["score"]:
        unique[url] = item

candidates = sorted(
    unique.values(),
    key=lambda item: (-item["score"], item["name"].lower()),
)

test_lines = ["#EXTM3U"]
report_lines = [
    "BrandenTV Local WABC Search",
    "=" * 80,
    f"Files scanned: {len(files)}",
    f"Raw matches: {len(raw)}",
    f"Unique candidates: {len(candidates)}",
    "",
]

for number, item in enumerate(candidates, 1):
    label = (
        f'{number:03d} - {item["name"]} '
        f'[score {item["score"]}]'
    )

    test_lines.extend([
        f'#EXTINF:-1 group-title="Local WABC Test",{label}',
        item["url"],
    ])

    report_lines.extend([
        "=" * 80,
        f'{number:03d}. {item["name"]}',
        f'Score:  {item["score"]}',
        f'Source: {item["source"]}',
        f'URL:    {item["url"]}',
        "",
    ])

TEST.write_text("\n".join(test_lines) + "\n", encoding="utf-8")
REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
JSON_OUT.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")

print("Files scanned:", len(files))
print("Raw matches:", len(raw))
print("Unique candidates:", len(candidates))
print("Test playlist:", TEST)
print("Report:", REPORT)
print("JSON:", JSON_OUT)
