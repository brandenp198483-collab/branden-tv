import json, gzip, urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path("epg_sources.json")

candidates = {
    "pluto": "https://i.mjh.nz/PlutoTV/us.xml.gz",
    "samsung": "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
    "plex": "https://i.mjh.nz/Plex/us.xml.gz",
    "xumo_mjh": "https://i.mjh.nz/XumoTV/us.xml.gz",
    "roku_mjh": "https://i.mjh.nz/Roku/us.xml.gz",
    "stirr_mjh": "https://i.mjh.nz/Stirr/us.xml.gz",
    "pbs_mjh": "https://i.mjh.nz/PBS/us.xml.gz"
}

good = {}

for name, url in candidates.items():
    print("Testing", name, url)
    try:
        data = urllib.request.urlopen(url, timeout=20).read()
        if url.endswith(".gz"):
            data = gzip.decompress(data)

        root = ET.fromstring(data)
        channels = len(root.findall("channel"))
        programmes = len(root.findall("programme"))

        if root.tag == "tv" and channels > 0 and programmes > 0:
            print(f"  OK channels={channels} programmes={programmes}")
            good[name] = url
        else:
            print(f"  BAD channels={channels} programmes={programmes}")

    except Exception as e:
        print("  FAILED", e)

OUT.write_text(json.dumps(good, indent=2) + "\n")
print()
print("Wrote", OUT)
print("Good EPG sources:", len(good))
