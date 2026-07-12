#!/usr/bin/env python3

import re
from pathlib import Path

PRODUCTION = Path("docs/BrandenTV-Stremio.m3u")
OVERRIDES = Path("playlists/manual_overrides.m3u")

TEST_OUT = Path("docs/BrandenTV-All-Streams-Audit.m3u")
REPORT_OUT = Path("docs/all-streams-audit-report.txt")

def attr(line, key):
    match = re.search(rf'{re.escape(key)}="([^"]*)"', line)
    return match.group(1).strip() if match else ""

def parse_playlist(path):
    entries = []
    lines = path.read_text(errors="ignore").splitlines()

    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF") or "," not in line:
            continue

        name = line.rsplit(",", 1)[-1].strip()
        url = ""

        for next_line in lines[i + 1:i + 8]:
            next_line = next_line.strip()

            if next_line.startswith(("http://", "https://")):
                url = next_line
                break

            if next_line.startswith("#EXTINF"):
                break

        entries.append({
            "name": name,
            "url": url,
            "group": attr(line, "group-title") or "Uncategorized",
            "tvg_id": attr(line, "tvg-id"),
            "logo": attr(line, "tvg-logo"),
            "info": line,
        })

    return entries

production = parse_playlist(PRODUCTION)
manual = parse_playlist(OVERRIDES) if OVERRIDES.exists() else []

manual_by_name = {item["name"]: item["url"] for item in manual}
manual_urls = {item["url"] for item in manual if item["url"]}

test_lines = ["#EXTM3U"]
report_lines = [
    "BrandenTV Full Stream Audit",
    "=" * 90,
    f"Production channels: {len(production)}",
    f"Manual overrides: {len(manual)}",
    "",
]

for number, item in enumerate(production, 1):
    locked = (
        item["name"] in manual_by_name
        and manual_by_name[item["name"]] == item["url"]
    ) or item["url"] in manual_urls

    status = "LOCKED" if locked else "AUTO-SELECTED"
    safe_name = item["name"].replace(",", " ")

    attributes = [
        '#EXTINF:-1',
        f'group-title="Full Stream Audit - {item["group"]}"',
    ]

    if item["logo"]:
        attributes.append(f'tvg-logo="{item["logo"]}"')

    label = (
        f'{number:03d} - {safe_name} '
        f'[{status}]'
    )

    test_lines.append(" ".join(attributes) + "," + label)
    test_lines.append(item["url"])

    report_lines.extend([
        "=" * 90,
        f"{number:03d}. {item['name']}",
        f"Group:   {item['group']}",
        f"Status:  {status}",
        f"TVG ID:  {item['tvg_id']}",
        f"URL:     {item['url']}",
        "",
    ])

TEST_OUT.write_text("\n".join(test_lines) + "\n", encoding="utf-8")
REPORT_OUT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

locked_count = sum(
    1 for item in production
    if (
        item["name"] in manual_by_name
        and manual_by_name[item["name"]] == item["url"]
    ) or item["url"] in manual_urls
)

print("Created:", TEST_OUT)
print("Created:", REPORT_OUT)
print("Total channels:", len(production))
print("Locked channels:", locked_count)
print("Auto-selected channels:", len(production) - locked_count)
