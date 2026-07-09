import re
from pathlib import Path

targets = [
    "AccuWeather Network","AXS TV","AMC","Bravo","CBS","CMT",
    "Comedy Central","TNT","Discovery Channel","Lifetime",
    "USA Network","H2","History Channel","MTV","Nickelodeon","Laff","Ovation","Discovery Channel","Lifetime"
]

m3u = Path("output/BrandenTV-Stremio.m3u").read_text(errors="ignore").splitlines()

for i,line in enumerate(m3u):
    if not line.startswith("#EXTINF"):
        continue
    name = line.split(",",1)[-1].strip()
    if name in targets:
        print("="*60)
        print(name)
        print(line)
        if i+1 < len(m3u):
            print(m3u[i+1])
