#!/usr/bin/env python3

import glob
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPORT = Path("docs/local-mgm-search-report.txt")
JSON_OUT = Path("docs/local-mgm-search-candidates.json")
TEST_OUT = Path("docs/BrandenTV-Local-MGM-Test.m3u")

PLAYLIST_PATTERNS = [
    "playlists/*.m3u",
    "playlists/*.m3u8",
    "sources/*.m3u",
    "sources/*.m3u8",
    "scan_cache/*.m3u",
    "scan_cache/*.m3u8",
    "github_m3u_cache/**/*.m3u",
    "github_m3u_cache/**/*.m3u8",
]

JSON_FILES = [
    "channel_database.json",
    "broad_usa_candidates.json",
    "hunter_mode_candidates.json",
    "verified_channels.json",
]

SEARCH_PATTERNS = [
    r"\bmgm\s*\+",
    r"\bmgm\s+plus\b",
    r"\bmgmplus\b",
    r"\bepix\b",
    r"\bepix\s*2\b",
    r"\bepix\s*hits\b",
    r"\bepix\s*drive[\s-]*in\b",
    r"\bmgm\s*hits\b",
    r"\bmgm\s*marquee\b",
    r"\bmgm\s*drive[\s-]*in\b",
    r"\bmgm\s*east\b",
    r"\bmgm\s*west\b",
]

REJECT_TERMS = [
    "latino",
    "latam",
    "espanol",
    "español",
    "brasil",
    "brazil",
    "india",
    "pakistan",
    "philippines",
    "arabic",
    "turkey",
    "korea",
    "japan",
    "127.0.0.1",
    "localhost",
    "192.168.",
    "10.0.",
    "youtube.com",
    "youtu.be",
]

QUALITY_POINTS = {
    "2160": 60,
    "4k": 60,
    "uhd": 55,
    "1080p": 50,
    "1080": 45,
    "fhd": 45,
    "720p": 35,
    "720": 30,
    "hd": 25,
    "480p": 12,
    "480": 10,
    "360p": 5,
    "360": 4,
    "hevc": 12,
    "h265": 12,
    "h264": 6,
    "vip": 6,
    "backup": 4,
    "east": 20,
    "west": -15,
    "usa": 30,
    " us ": 25,
}

def normalize_url(url):
    url = (url or "").strip()

    for marker in (".m3u8:", ".mpd:", ".ts:"):
        pos = url.lower().find(marker)
        if pos != -1:
            url = url[:pos + len(marker) - 1]
            break

    return url.rstrip("),.;]")

def url_key(url):
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return url

def is_match(text):
    return any(re.search(pattern, text, flags=re.I) for pattern in SEARCH_PATTERNS)

def classify(name):
    clean = re.sub(r"[^a-z0-9+]+", " ", (name or "").lower()).strip()

    if "drive in" in clean or "drive-in" in clean:
        return "MGM+ Drive-In"
    if "marquee" in clean:
        return "MGM+ Marquee"
    if "hits" in clean:
        return "MGM+ Hits"
    if "epix 2" in clean or "epix2" in clean:
        return "MGM+ 2"
    if "west" in clean:
        return "MGM+ West"
    return "MGM+ East"

def score(name, url, source):
    text = f" {name} {url} {source} ".lower()
    clean_name = re.sub(r"[^a-z0-9+]+", " ", (name or "").lower()).strip()

    total = 0

    exact_names = {
        "mgm+",
        "mgm plus",
        "epix",
        "mgm+ east",
        "mgm+ hits",
        "mgm+ marquee",
        "mgm+ drive in",
        "epix hits",
        "epix drive in",
    }

    if clean_name in exact_names:
        total += 100

    for term, points in QUALITY_POINTS.items():
        if term in text:
            total += points

    if url.lower().endswith(".m3u8"):
        total += 25
    elif url.lower().endswith(".ts"):
        total += 15
    elif ".mpd" in url.lower():
        total += 10

    if url.startswith("https://"):
        total += 5

    if any(term in text for term in REJECT_TERMS):
        total -= 1000

    return total

def parse_m3u(path):
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return []

    found = []

    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF") or "," not in line:
            continue

        name = line.rsplit(",", 1)[-1].strip()
        info = line
        url = ""

        for nxt in lines[i + 1:i + 8]:
            nxt = nxt.strip()

            if nxt.startswith(("http://", "https://")):
                url = normalize_url(nxt)
                break

            if nxt.startswith("#EXTINF"):
                break

        if not url:
            continue

        combined = f"{name} {info} {url}"

        if is_match(combined):
            found.append({
                "name": name or "MGM candidate",
                "url": url,
                "source": str(path),
                "info": info,
            })

    return found

def walk_json(obj, source):
    found = []

    if isinstance(obj, dict):
        name = (
            obj.get("name")
            or obj.get("channel")
            or obj.get("title")
            or obj.get("raw_name")
            or ""
        )

        url = (
            obj.get("url")
            or obj.get("stream_url")
            or obj.get("stream")
            or ""
        )

        if isinstance(name, str) and isinstance(url, str):
            combined = f"{name} {url} {json.dumps(obj, ensure_ascii=False)}"

            if url.startswith(("http://", "https://")) and is_match(combined):
                found.append({
                    "name": name.strip() or "MGM candidate",
                    "url": normalize_url(url),
                    "source": source,
                    "info": "",
                })

        for value in obj.values():
            found.extend(walk_json(value, source))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(walk_json(item, source))

    return found

playlist_files = []

for pattern in PLAYLIST_PATTERNS:
    playlist_files.extend(glob.glob(pattern, recursive=True))

playlist_files = sorted(set(playlist_files))

raw = []

for filename in playlist_files:
    raw.extend(parse_m3u(Path(filename)))

for filename in JSON_FILES:
    path = Path(filename)

    if not path.exists():
        continue

    try:
        raw.extend(
            walk_json(
                json.loads(path.read_text(errors="ignore")),
                filename,
            )
        )
    except Exception as exc:
        print(f"SKIP JSON {filename}: {exc}")

deduped = {}

for item in raw:
    item["category"] = classify(item["name"])
    item["score"] = score(item["name"], item["url"], item["source"])

    key = url_key(item["url"])

    if key not in deduped or item["score"] > deduped[key]["score"]:
        deduped[key] = item

candidates = list(deduped.values())
candidates.sort(
    key=lambda item: (
        item["score"] < 0,
        item["category"],
        -item["score"],
        item["name"].lower(),
    )
)

JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
JSON_OUT.write_text(json.dumps(candidates, indent=2) + "\n")

report = [
    "BrandenTV Local MGM / MGM+ / EPIX Search",
    "=" * 78,
    f"Playlist files scanned: {len(playlist_files)}",
    f"Raw matches: {len(raw)}",
    f"Unique candidates: {len(candidates)}",
    "",
]

test = ["#EXTM3U"]
test_count = 0

for number, item in enumerate(candidates, 1):
    report.extend([
        "=" * 78,
        f"{number:03d}. {item['name']}",
        f"Category: {item['category']}",
        f"Score: {item['score']}",
        f"Source: {item['source']}",
        f"URL: {item['url']}",
        "",
    ])

    if item["score"] < 0:
        continue

    test_count += 1
    safe_name = item["name"].replace(",", " ")

    test.extend([
        (
            '#EXTINF:-1 group-title="Local MGM Test",'
            f'{test_count:03d} - {item["category"]} — '
            f'{safe_name} [score {item["score"]}]'
        ),
        item["url"],
    ])

REPORT.write_text("\n".join(report) + "\n")
TEST_OUT.write_text("\n".join(test) + "\n")

print("Playlist files scanned:", len(playlist_files))
print("Raw matches:", len(raw))
print("Unique candidates:", len(candidates))
print("Test candidates:", test_count)
print("Report:", REPORT)
print("JSON:", JSON_OUT)
print("Test playlist:", TEST_OUT)
