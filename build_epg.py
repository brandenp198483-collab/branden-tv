from pathlib import Path
import re
import html

PLAYLIST = Path("docs/BrandenTV-Stremio.m3u")
OUT = Path("docs/BrandenTV.xml")

def attr(line, key):
    m = re.search(rf'{key}="([^"]*)"', line)
    return m.group(1).strip() if m else ""

channels = []

for line in PLAYLIST.read_text(errors="ignore").splitlines():
    if not line.startswith("#EXTINF"):
        continue

    tvg_id = attr(line, "tvg-id")
    logo = attr(line, "tvg-logo")
    name = line.split(",", 1)[-1].strip()

    if not tvg_id:
        safe = re.sub(r"[^A-Za-z0-9]+", ".", name).strip(".")
        tvg_id = safe + ".branden"

    channels.append({
        "id": tvg_id,
        "name": name,
        "logo": logo
    })

seen = set()
unique = []
for ch in channels:
    if ch["id"] in seen:
        continue
    seen.add(ch["id"])
    unique.append(ch)

out = ['<?xml version="1.0" encoding="UTF-8"?>']
out.append('<tv generator-info-name="BrandenTV">')

for ch in unique:
    cid = html.escape(ch["id"], quote=True)
    name = html.escape(ch["name"])
    out.append(f'  <channel id="{cid}">')
    out.append(f'    <display-name>{name}</display-name>')
    if ch["logo"]:
        out.append(f'    <icon src="{html.escape(ch["logo"], quote=True)}" />')
    out.append('  </channel>')

out.append('</tv>')
OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

print(f"Wrote {OUT}")
print(f"Channels: {len(unique)}")
