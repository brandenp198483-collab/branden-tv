#!/usr/bin/env python3

from pathlib import Path
import re

OUT = Path("docs/BrandenTV-WFLA-Expanded-Test.m3u")
REPORT = Path("docs/wfla-expanded-test-report.txt")

keywords = (
    "wfla",
    "nbc-8-tampa",
    "nbc-tampa",
    "news-channel-8",
    "newschannel-8",
    "tampa-nbc",
)

sources = [
    path
    for path in Path("docs").glob("BrandenTV-GitHub-*-Test.m3u")
    if any(keyword in path.name.lower() for keyword in keywords)
]

entries = []
seen_urls = set()

for path in sorted(sources):
    lines = path.read_text(errors="ignore").splitlines()

    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF"):
            continue

        if index + 1 >= len(lines):
            continue

        url = lines[index + 1].strip()

        if not url.startswith(("http://", "https://")):
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        name = (
            line.rsplit(",", 1)[-1].strip()
            if "," in line
            else path.stem
        )

        entries.append((name, url, str(path)))

playlist = ["#EXTM3U"]
report = [
    "WFLA expanded candidate test",
    "=" * 78,
    f"Source playlists examined: {len(sources)}",
    f"Unique candidates: {len(entries)}",
    "",
]

for number, (name, url, source) in enumerate(entries, 1):
    clean_name = re.sub(r"\s+", " ", name).replace(",", " ").strip()

    playlist.extend([
        (
            '#EXTINF:-1 group-title="WFLA Expanded Test",'
            f"{number:03d} - {clean_name}"
        ),
        url,
    ])

    report.extend([
        "=" * 78,
        f"{number:03d}. {name}",
        f"Source: {source}",
        f"URL: {url}",
        "",
    ])

OUT.write_text("\n".join(playlist) + "\n", encoding="utf-8")
REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

print("Source playlists examined:", len(sources))
print("Unique candidates:", len(entries))
print("Playlist:", OUT)
print("Report:", REPORT)
