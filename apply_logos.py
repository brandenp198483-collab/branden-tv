import json
import re
from pathlib import Path

BASE_URL = "https://brandenp198483-collab.github.io/branden-tv/logos"
MAP_FILE = Path("config/channel_logos.json")

FILES = [
    Path("output/BrandenTV-Stremio.m3u"),
    Path("docs/BrandenTV-Stremio.m3u"),
]

logo_map = json.loads(MAP_FILE.read_text())

for playlist in FILES:
    if not playlist.exists():
        print("SKIP:", playlist)
        continue

    lines = playlist.read_text(errors="ignore").splitlines()
    output = []

    for line in lines:
        if not line.startswith("#EXTINF") or "," not in line:
            output.append(line)
            continue

        channel = line.rsplit(",", 1)[-1].strip()
        filename = logo_map.get(channel)

        if not filename:
            output.append(line)
            continue

        logo_url = f"{BASE_URL}/{filename}"

        if re.search(r'\btvg-logo="[^"]*"', line):
            line = re.sub(
                r'\btvg-logo="[^"]*"',
                f'tvg-logo="{logo_url}"',
                line,
                count=1,
            )
        else:
            line = line.replace(
                "#EXTINF:-1",
                f'#EXTINF:-1 tvg-logo="{logo_url}"',
                1,
            )

        output.append(line)

    playlist.write_text("\n".join(output) + "\n")
    print("Updated:", playlist)
