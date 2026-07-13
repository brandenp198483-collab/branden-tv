#!/usr/bin/env python3

import re
import shutil
from datetime import datetime
from pathlib import Path

OLD_NAME = "AMC"
NEW_NAME = "AMC+"
NEW_TVG_ID = "AMC.Plus.branden"

EXPECTED_URL = "http://40.160.24.52/AMC_PLUS/index.m3u8"

PLAYLISTS = [
    Path("output/BrandenTV-Stremio.m3u"),
    Path("docs/BrandenTV-Stremio.m3u"),
]

OVERRIDES = Path("playlists/manual_overrides.m3u")
BACKUP_DIR = Path("docs/backups")

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")


def channel_name(line: str) -> str:
    if not line.startswith("#EXTINF") or "," not in line:
        return ""

    return line.rsplit(",", 1)[-1].strip()


def replace_attribute(line: str, key: str, value: str) -> str:
    pattern = rf'{re.escape(key)}="[^"]*"'

    if re.search(pattern, line):
        return re.sub(pattern, f'{key}="{value}"', line)

    comma = line.rfind(",")

    if comma == -1:
        raise SystemExit(f"Malformed EXTINF line: {line}")

    return line[:comma] + f' {key}="{value}"' + line[comma:]


for path in PLAYLISTS:
    if not path.exists():
        raise SystemExit(f"Missing playlist: {path}")

    shutil.copy2(
        path,
        BACKUP_DIR / f"{path.name}.AMC.{timestamp}.bak",
    )

    lines = path.read_text(errors="ignore").splitlines()

    old_matches = []
    new_matches = []

    for index, line in enumerate(lines):
        name = channel_name(line)

        if name == OLD_NAME:
            old_matches.append(index)

        elif name == NEW_NAME:
            new_matches.append(index)

    if len(old_matches) != 1:
        raise SystemExit(
            f"Safety stop in {path}: expected exactly one AMC entry, "
            f"found {len(old_matches)}"
        )

    if new_matches:
        raise SystemExit(
            f"Safety stop in {path}: AMC+ already exists"
        )

    index = old_matches[0]

    if index + 1 >= len(lines):
        raise SystemExit(f"Missing AMC URL in {path}")

    current_url = lines[index + 1].strip()

    if current_url != EXPECTED_URL:
        raise SystemExit(
            f"Safety stop in {path}: unexpected AMC URL:\n"
            f"{current_url}"
        )

    info = lines[index]
    info = replace_attribute(info, "tvg-id", NEW_TVG_ID)
    info = replace_attribute(info, "tvg-name", NEW_NAME)
    info = info.rsplit(",", 1)[0] + "," + NEW_NAME

    lines[index] = info

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"{path}: renamed exactly one AMC entry to AMC+")


if not OVERRIDES.exists():
    raise SystemExit(f"Missing overrides file: {OVERRIDES}")

shutil.copy2(
    OVERRIDES,
    BACKUP_DIR / f"{OVERRIDES.name}.AMC.{timestamp}.bak",
)

override_lines = OVERRIDES.read_text(errors="ignore").splitlines()

existing_names = [
    channel_name(line)
    for line in override_lines
    if line.startswith("#EXTINF")
]

if NEW_NAME in existing_names:
    raise SystemExit("Safety stop: AMC+ already exists in manual overrides")

if OLD_NAME in existing_names:
    raise SystemExit("Safety stop: AMC already exists in manual overrides")

override_lines.extend([
    (
        f'#EXTINF:-1 tvg-id="{NEW_TVG_ID}" '
        f'tvg-name="{NEW_NAME}" '
        f'group-title="Entertainment",{NEW_NAME}'
    ),
    EXPECTED_URL,
])

OVERRIDES.write_text(
    "\n".join(override_lines) + "\n",
    encoding="utf-8",
)

print("manual_overrides.m3u: added and locked AMC+")
print()
print("Stream:", EXPECTED_URL)
print("EPG files were not touched.")
