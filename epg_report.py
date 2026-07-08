from pathlib import Path
import re
import xml.etree.ElementTree as ET

PLAYLIST = Path("docs/BrandenTV-Stremio.m3u")
EPG = Path("docs/BrandenTV.xml")
OUT = Path("docs/epg_report.txt")

def attr(line, key):
    m = re.search(rf'{key}="([^"]*)"', line)
    return m.group(1).strip() if m else ""

playlist_channels = []

for line in PLAYLIST.read_text(errors="ignore").splitlines():
    if line.startswith("#EXTINF"):
        tvg_id = attr(line, "tvg-id")
        name = line.split(",", 1)[-1].strip()
        playlist_channels.append((name, tvg_id))

root = ET.parse(EPG).getroot()

program_counts = {}
for p in root.findall("programme"):
    cid = p.attrib.get("channel", "")
    program_counts[cid] = program_counts.get(cid, 0) + 1

matched = []
missing = []

for name, tvg_id in playlist_channels:
    count = program_counts.get(tvg_id, 0)
    if count:
        matched.append((name, tvg_id, count))
    else:
        missing.append((name, tvg_id))

lines = []
lines.append("=============================================")
lines.append("        BrandenTV EPG COVERAGE REPORT")
lines.append("=============================================")
lines.append("")
lines.append(f"Playlist channels: {len(playlist_channels)}")
lines.append(f"Channels with EPG: {len(matched)}")
lines.append(f"Channels missing EPG: {len(missing)}")
pct = (len(matched) / len(playlist_channels) * 100) if playlist_channels else 0
lines.append(f"EPG coverage: {pct:.1f}%")
lines.append("")
lines.append("CHANNELS WITH EPG:")
for name, tvg_id, count in sorted(matched):
    lines.append(f"- {name} | {tvg_id} | programmes={count}")

lines.append("")
lines.append("CHANNELS MISSING EPG:")
for name, tvg_id in sorted(missing):
    lines.append(f"- {name} | {tvg_id}")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"Wrote {OUT}")
