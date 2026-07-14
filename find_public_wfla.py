#!/usr/bin/env python3

import re
from pathlib import Path
from urllib.parse import urlparse

OUT = Path("docs/BrandenTV-WFLA-Public-Test.m3u")
REPORT = Path("docs/wfla-public-test-report.txt")

ROOTS = [
    Path("playlists"),
    Path("github_m3u_cache"),
    Path("docs"),
]

WANTED = re.compile(
    r"\bWFLA\b|"
    r"NBC\s*8\s*Tampa|"
    r"NBC\s*Tampa(?:\s*Bay)?|"
    r"News\s*Channel\s*8|"
    r"WFLA[- ]?DT1",
    re.I,
)

REJECT_NAME = re.compile(
    r"\b970\s*AM\b|"
    r"\bWLIO\b|"
    r"\bLima\b|"
    r"FOX|CBS|ABC|PBS|TBCN",
    re.I,
)

PREFERRED_HOST_TERMS = (
    "amagi",
    "cloudfront",
    "uplynk",
    "wurl",
    "tubi",
    "localnow",
    "roku",
    "samsung",
    "pluto",
    "plex",
    "xumo",
    "akamai",
    "fastly",
    "moveonjoy",
)

def looks_credentialed(url):
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]

    # Common Xtream-style pattern: /live/user/password/channel
    if len(parts) >= 4 and parts[0].lower() == "live":
        return True

    if "@" in parsed.path:
        return True

    return False

entries = []
seen = set()
files_scanned = 0

for root in ROOTS:
    if not root.exists():
        continue

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in {".m3u", ".m3u8", ".txt"}:
            continue

        files_scanned += 1

        try:
            lines = path.read_text(errors="ignore").splitlines()
        except Exception:
            continue

        for i, line in enumerate(lines):
            if not line.startswith("#EXTINF") or "," not in line:
                continue

            name = line.rsplit(",", 1)[-1].strip()

            if not WANTED.search(name) or REJECT_NAME.search(name):
                continue

            url = ""

            for candidate in lines[i + 1:i + 6]:
                candidate = candidate.strip()

                if candidate.startswith(("http://", "https://")):
                    url = candidate
                    break

                if candidate.startswith("#EXTINF"):
                    break

            if not url or url in seen:
                continue

            if looks_credentialed(url):
                continue

            host = urlparse(url).netloc.lower()
            preferred = any(term in host or term in url.lower()
                            for term in PREFERRED_HOST_TERMS)

            score = 100 if preferred else 40

            if "wfla" in name.lower():
                score += 50

            if "dt1" in name.lower():
                score += 20

            seen.add(url)
            entries.append({
                "name": name,
                "url": url,
                "source": str(path),
                "score": score,
            })

entries.sort(key=lambda item: (-item["score"], item["name"].lower()))

playlist = ["#EXTM3U"]
report = [
    "WFLA public-source candidate search",
    "=" * 78,
    f"Files scanned: {files_scanned}",
    f"Candidates: {len(entries)}",
    "",
]

for number, item in enumerate(entries, 1):
    clean = item["name"].replace(",", " ")

    playlist.extend([
        f'#EXTINF:-1 group-title="WFLA Public Test",'
        f'{number:03d} - {clean} [score {item["score"]}]',
        item["url"],
    ])

    report.extend([
        "=" * 78,
        f'{number:03d}. {item["name"]}',
        f'Score: {item["score"]}',
        f'Source: {item["source"]}',
        f'URL: {item["url"]}',
        "",
    ])

OUT.write_text("\n".join(playlist) + "\n", encoding="utf-8")
REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

print("Files scanned:", files_scanned)
print("Public candidates:", len(entries))
print("Playlist:", OUT)
print("Report:", REPORT)
