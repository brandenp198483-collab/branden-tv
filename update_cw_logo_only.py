#!/usr/bin/env python3

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

CHANNEL_NAME = "The CW"
SOURCE_EPG_ID = "CWForever.us"

EPG_EXTRACT = Path("docs/epg-extracts/the-cw-forever.xml")

PLAYLISTS = [
    Path("output/BrandenTV-Stremio.m3u"),
    Path("docs/BrandenTV-Stremio.m3u"),
]

BACKUP_DIR = Path("docs/backups")


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def get_channel_name(line: str) -> str:
    if not line.startswith("#EXTINF") or "," not in line:
        return ""

    return line.rsplit(",", 1)[-1].strip()


def find_epg_icon() -> str:
    if not EPG_EXTRACT.exists():
        raise SystemExit(f"Missing EPG extract: {EPG_EXTRACT}")

    root = ET.parse(EPG_EXTRACT).getroot()

    matching_channels = [
        element
        for element in root
        if local_tag(element.tag) == "channel"
        and element.attrib.get("id") == SOURCE_EPG_ID
    ]

    if len(matching_channels) != 1:
        raise SystemExit(
            f"Safety stop: expected exactly one {SOURCE_EPG_ID} channel "
            f"in {EPG_EXTRACT}, found {len(matching_channels)}"
        )

    icons = [
        child.attrib.get("src", "").strip()
        for child in matching_channels[0]
        if local_tag(child.tag) == "icon"
        and child.attrib.get("src", "").strip()
    ]

    if len(icons) != 1:
        raise SystemExit(
            f"Safety stop: expected exactly one icon for {SOURCE_EPG_ID}, "
            f"found {len(icons)}"
        )

    icon_url = icons[0]

    if not icon_url.startswith(("http://", "https://")):
        raise SystemExit(f"Safety stop: invalid icon URL: {icon_url}")

    return icon_url


def inspect_playlist(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing playlist: {path}")

    lines = path.read_text(errors="ignore").splitlines()

    matches = [
        index
        for index, line in enumerate(lines)
        if get_channel_name(line) == CHANNEL_NAME
    ]

    if len(matches) != 1:
        raise SystemExit(
            f"Safety stop in {path}: expected exactly one {CHANNEL_NAME} "
            f"entry, found {len(matches)}"
        )

    index = matches[0]

    if index + 1 >= len(lines):
        raise SystemExit(
            f"Safety stop in {path}: {CHANNEL_NAME} has no stream URL"
        )

    stream_url = lines[index + 1].strip()

    if not stream_url.startswith(("http://", "https://")):
        raise SystemExit(
            f"Safety stop in {path}: invalid stream URL after {CHANNEL_NAME}"
        )

    return {
        "path": path,
        "lines": lines,
        "index": index,
        "original_info": lines[index],
        "stream_url": stream_url,
    }


icon_url = find_epg_icon()
states = [inspect_playlist(path) for path in PLAYLISTS]

stream_urls = {state["stream_url"] for state in states}

if len(stream_urls) != 1:
    raise SystemExit(
        "Safety stop: The CW stream URLs differ between playlists:\n"
        + "\n".join(sorted(stream_urls))
    )

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

for state in states:
    path = state["path"]
    lines = state["lines"]
    index = state["index"]
    old_info = state["original_info"]

    if re.search(r'tvg-logo="[^"]*"', old_info):
        new_info = re.sub(
            r'tvg-logo="[^"]*"',
            f'tvg-logo="{icon_url}"',
            old_info,
            count=1,
        )
    else:
        comma = old_info.rfind(",")

        if comma == -1:
            raise SystemExit(
                f"Safety stop in {path}: malformed EXTINF line"
            )

        new_info = (
            old_info[:comma]
            + f' tvg-logo="{icon_url}"'
            + old_info[comma:]
        )

    # Confirm the channel name portion did not change.
    if get_channel_name(new_info) != CHANNEL_NAME:
        raise SystemExit(
            f"Safety stop in {path}: channel name would change"
        )

    # Confirm that removing only tvg-logo makes the lines identical.
    def without_logo(value: str) -> str:
        value = re.sub(r'\s*tvg-logo="[^"]*"', "", value)
        return re.sub(r"\s+", " ", value).strip()

    if without_logo(old_info) != without_logo(new_info):
        raise SystemExit(
            f"Safety stop in {path}: something besides tvg-logo changed"
        )

    shutil.copy2(
        path,
        BACKUP_DIR / f"{path.name}.The-CW-logo.{stamp}.bak",
    )

    lines[index] = new_info
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Updated logo only: {path}")
    print("Before:", old_info)
    print("After: ", new_info)
    print("Stream unchanged:", state["stream_url"])
    print()

print("CW EPG icon:", icon_url)
print("Channels renamed: 0")
print("Streams changed: 0")
print("Other channel entries changed: 0")
