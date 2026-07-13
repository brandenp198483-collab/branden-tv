#!/usr/bin/env python3

import shutil
from datetime import datetime
from pathlib import Path

CHANNEL = "AMC"
TVG_ID = "AMC.branden"
URL = "http://s.rocketdns.info:8080/monstercable/Dq6jjknxCr/643834"
LOGO = "https://brandenp198483-collab.github.io/branden-tv/logos/amc.png"

FILES = [
    Path("playlists/manual_overrides.m3u"),
    Path("output/BrandenTV-Stremio.m3u"),
    Path("docs/BrandenTV-Stremio.m3u"),
]

backup_dir = Path("docs/backups")
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

for path in FILES:
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")

    lines = path.read_text(errors="ignore").splitlines()

    names = [
        line.rsplit(",", 1)[-1].strip()
        for line in lines
        if line.startswith("#EXTINF") and "," in line
    ]

    if CHANNEL in names:
        raise SystemExit(
            f"Safety stop: {CHANNEL} already exists in {path}"
        )

    if "AMC+" not in names and path.name != "manual_overrides.m3u":
        raise SystemExit(
            f"Safety stop: AMC+ unexpectedly missing from {path}"
        )

    shutil.copy2(
        path,
        backup_dir / f"{path.name}.AMC.{stamp}.bak",
    )

    if path.name == "manual_overrides.m3u":
        entry = [
            (
                f'#EXTINF:-1 tvg-id="{TVG_ID}" '
                f'tvg-name="{CHANNEL}" '
                f'group-title="Entertainment",{CHANNEL}'
            ),
            URL,
        ]
    else:
        entry = [
            (
                f'#EXTINF:-1 tvg-id="{TVG_ID}" '
                f'tvg-name="{CHANNEL}" '
                f'tvg-logo="{LOGO}" '
                f'group-title="Entertainment",{CHANNEL}'
            ),
            URL,
        ]

    lines.extend(entry)

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"{path}: added exactly one AMC entry")

print()
print("AMC+ was not changed.")
print("EPG was not changed.")
print("AMC stream:", URL)
