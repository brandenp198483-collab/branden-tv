import re
import json
import gzip
import urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = "https://epgshare01.online/epgshare01/"
OUT = Path("epgshare_candidates.json")

headers = {"User-Agent": "Mozilla/5.0"}

preferred = [
    "DIRECTV","DISH","YOUTUBE","FUBO","HULU","SLING",
    "XFINITY","COMCAST","SPECTRUM","FRNDLY","PHILO",
    "PLUTO","PLEX","SAMSUNG","ROKU","XUMO"
]

print("Downloading index...")

req = urllib.request.Request(BASE, headers=headers)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8","ignore")

files = sorted(set(re.findall(r'href="([^"]+\.xml\.gz)"', html, re.I)))
picked = [f for f in files if any(x in f.upper() for x in preferred)]

print("Found", len(files), "files")
print("Testing", len(picked), "preferred files")

good = {}

for f in picked:
    url = BASE + f
    print("Testing", f)

    try:
        req = urllib.request.Request(url, headers=headers)
        data = urllib.request.urlopen(req, timeout=30).read()

        if url.endswith(".gz"):
            data = gzip.decompress(data)

        root = ET.fromstring(data)

        channels = len(root.findall("channel"))
        programmes = len(root.findall("programme"))

        if channels and programmes:
            print(f"  OK channels={channels} programmes={programmes}")
            good[f] = url
        else:
            print("  Empty")

    except Exception as e:
        print("  FAILED", e)

OUT.write_text(json.dumps(good, indent=2))
print("\nSaved", OUT)
print("Working sources:", len(good))
