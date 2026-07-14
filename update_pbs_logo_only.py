#!/usr/bin/env python3

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

CHANNEL_NAME = "PBS"
SOURCE_EPG_ID = "PBSKidsWBIQDT2.us"
EPG_EXTRACT = Path("docs/epg-extracts/pbs-kids-wbiq.xml")

PLAYLISTS = [
    Path("output/BrandenTV
cd ~/branden-tv

cat > update_pbs_logo_only.py <<'PY'
#!/usr/bin/env python3

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

CHANNEL_NAME = "PBS"
SOURCE_EPG_ID = "PBSKidsWBIQDT2.us"
EPG_EXTRACT = Path("docs/epg-extracts/pbs-kids-wbiq.xml")

PLAYLISTS = [
    Path("output/BrandenTV-Stremio.m3u"),
    Path("docs/BrandenTV-Stremio.m3u"),
]

BACKUP_DIR = Path("docs/backups")


def tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def channel_name(line: str) -> str:
    if not line.startswith("#EXTINF") or "," not in line:
        return ""
    return line.rsplit(",", 1)[-1].strip()


if not EPG_EXTRACT.exists():
    raise SystemExit(f"Missing extract: {EPG_EXTRACT}")

root = ET.parse(EPG_EXTRACT).getroot()

channel_nodes = [
    elem
    for elem in root
    if tag(elem.tag) == "channel"
    and elem.attrib.get("id") == SOURCE_EPG_ID
]

if len(channel_nodes) != 1:
    raise SystemExit(
        f"Safety stop: expected one {SOURCE_EPG_ID} channel node, "
        f"found {len(channel_nodes)}"
    )

icons = [
    child.attrib.get("src", "").strip()
    for child in channel_nodes[0]
    if tag(child.tag) == "icon"
    and child.attrib.get("src", "").strip()
]

if len(icons) != 1:
    raise SystemExit(
        f"Safety stop: expected one PBS icon, found {len(icons)}"
    )

icon_url = icons[0]

if not icon_url.startswith(("http://", "https://")):
    raise SystemExit(f"Invalid icon URL: {icon_url}")

states = []

for path in PLAYLISTS:
    if not path.exists():
        raise SystemExit(f"Missing playlist: {path}")

    lines = path.read_text(errors="ignore").splitlines()

    matches = [
        index
        for index, line in enumerate(lines)
        if channel_name(line) == CHANNEL_NAME
    ]

    if len(matches) != 1:
        raise SystemExit(
            f"Safety stop in {path}: expected exactly one PBS entry, "
            f"found {len(matches)}"
        )

    index = matches[0]

    if index + 1 >= len(lines):
        raise SystemExit(f"PBS stream missing in {path}")

    stream_url = lines[index + 1].strip()

    if not stream_url.startswith(("http://", "https://")):
        raise SystemExit(f"Invalid PBS stream in {path}")

    states.append({
        "path": path,
        "lines": lines,
        "index": index,
        "before": lines[index],
        "stream": stream_url,
    })

streams = {state["stream"] for state in states}

if len(streams) != 1:
    raise SystemExit(
        "Safety stop: PBS streams differ between playlist files:\n"
        + "\n".join(sorted(streams))
    )


def without_logo(line: str) -> str:
    line = re.sub(r'\s*tvg-logo="[^"]*"', "", line)
    return re.sub(r"\s+", " ", line).strip()


BACKUP_DIR.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

for state in states:
    path = state["path"]
    lines = state["lines"]
    index = state["index"]
    before = state["before"]

    if re.search(r'tvg-logo="[^"]*"', before):
        after = re.sub(
            r'tvg-logo="[^"]*"',
            f'tvg-logo="{icon_url}"',
            before,
            count=1,
        )
    else:
        comma = before.rfind(",")

        if comma == -1:
            raise SystemExit(f"Malformed PBS line in {path}")

        after = (
            before[:comma]
            + f' tvg-logo="{icon_url}"'
            + before[comma:]
        )

    if channel_name(after) != CHANNEL_NAME:
        raise SystemExit(f"Safety stop: PBS name would change in {path}")

    if without_logo(before) != without_logo(after):
        raise SystemExit(
            f"Safety stop: something besides the PBS logo would change in {path}"
        )

    shutil.copy2(
        path,
        BACKUP_DIR / f"{path.name}.PBS-logo.{stamp}.bak",
    )

    lines[index] = after
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Updated PBS logo only:", path)
    print("Before:", before)
    print("After: ", after)
    print("Stream unchanged:", state["stream"])
    print()

print("PBS logo:", icon_url)
print("Channels renamed: 0")
print("Streams changed: 0")
print("Other channels changed: 0")
