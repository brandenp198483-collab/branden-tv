import glob
import json
import re
from collections import defaultdict
from pathlib import Path

WHITELIST = Path("channel_whitelist.json")
ALIASES_FILE = Path("config/channel_aliases.json")
CURRENT_PLAYLIST = Path("output/BrandenTV-Stremio.m3u")
BAD_URL_FILES = [
    Path("config/bad_urls.txt"),
    Path("bad_urls.txt"),
    Path("playlists/bad_urls.txt"),
]

REPORT_OUT = Path("docs/hunter-mode-report.txt")
JSON_OUT = Path("hunter_mode_candidates.json")
PLAYLIST_OUT = Path("output/BrandenTV-Hunter-Test.m3u")

MAX_PER_CHANNEL = 5

QUALITY_SUFFIXES = [
    "",
    "HD",
    "SD",
    "FHD",
    "UHD",
    "4K",
    "1080",
    "1080p",
    "720",
    "720p",
    "576",
    "576p",
    "480",
    "480p",
    "360",
    "360p",
    "H264",
    "H265",
    "HEVC",
    "x265",
    "60fps",
    "East",
    "West",
    "US",
    "USA",
    "[US]",
    "VIP",
    "Backup",
    "Auto",
    "Live",
    "Main",
]

ALLOWED_EXTRA_WORDS = {
    "hd", "sd", "fhd", "uhd", "4k",
    "1080", "1080p", "720", "720p",
    "576", "576p", "480", "480p",
    "360", "360p",
    "h264", "h265", "hevc", "x265",
    "60fps", "east", "west",
    "us", "usa", "vip", "backup",
    "auto", "live", "main",
    "channel", "network",
}

BAD_REGION_WORDS = {
    "latin america", "latino", "latina",
    "espanol", "español", "spanish",
    "mexico", "méxico", "brazil", "brasil",
    "portugal", "india", "pakistan",
    "arabic", "africa", "asia",
    "korea", "japan", "turkey",
    "bulgaria", "romania", "russia",
}

SPECIFIC_REJECTS = {
    "Discovery Channel": {
        "turbo", "science", "family", "kids",
        "life", "asharq", "tudiscovery",
        "investigation discovery",
    },
    "AMC": {
        "thrillers", "reality", "cupid",
        "stories", "presents", "weddings",
        "absolute reality", "amc+", "amc plus",
    },
    "TNT": {
        "novelas", "kids", "sports",
        "music", "tntv",
    },
    "History Channel": {
        "history hit", "military history",
        "history and warfare",
    },
    "Food Network": {
        "food52", "food tv", "food channel",
    },
    "MLB Network": {
        "mlb channel", "mlb fast",
    },
}


def clean(text):
    text = text.lower()
    text = text.replace("&", " and ")
    text = text.replace("+", " plus ")
    text = text.replace("🇺🇸", " usa ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_lines(path):
    if not path.exists():
        return set()

    return {
        line.strip()
        for line in path.read_text(errors="ignore").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def parse_m3u(path):
    lines = path.read_text(errors="ignore").splitlines()
    channels = []

    for i, line in enumerate(lines):
        if not line.strip().startswith("#EXTINF"):
            continue

        info = line.strip()
        name = info.split(",")[-1].strip()
        url = ""

        for nxt in lines[i + 1:i + 8]:
            nxt = nxt.strip()

            if nxt.startswith("http://") or nxt.startswith("https://"):
                url = nxt

                suffix = ":" + name
                if url.lower().endswith(suffix.lower()):
                    url = url[:-len(suffix)]

                for marker in [".m3u8:", ".mpd:", ".ts:"]:
                    position = url.lower().find(marker)
                    if position != -1:
                        url = url[:position + len(marker) - 1]
                        break

                break

            if nxt.startswith("#EXTINF"):
                break

        if url:
            channels.append({
                "name": name,
                "info": info,
                "url": url,
                "source": path.stem,
                "file": str(path),
            })

    return channels


def current_channel_names():
    found = set()

    if not CURRENT_PLAYLIST.exists():
        return found

    for line in CURRENT_PLAYLIST.read_text(errors="ignore").splitlines():
        if line.startswith("#EXTINF") and "," in line:
            found.add(line.rsplit(",", 1)[-1].strip())

    return found


def base_aliases(wanted, whitelist, extra_aliases):
    aliases = {
        wanted,
        wanted.replace(" Channel", ""),
        wanted.replace(" Network", ""),
    }

    aliases.update(
        whitelist.get("aliases", {}).get(wanted, [])
    )
    aliases.update(extra_aliases.get(wanted, []))

    special = {
        "A&E": ["A and E", "AE", "A&E Network"],
        "Syfy": ["Sci Fi", "Sci-Fi", "SciFi"],
        "HBO2": ["HBO 2", "HBO Two"],
        "Investigation Discovery": [
            "ID Channel",
            "Investigation Discovery",
        ],
        "The Weather Channel": [
            "Weather Channel",
            "TWC",
        ],
        "Big Ten Network": [
            "BTN",
            "Big Ten Network",
        ],
    }

    aliases.update(special.get(wanted, []))

    return {clean(alias) for alias in aliases if clean(alias)}


def expanded_aliases(wanted, whitelist, extra_aliases):
    expanded = set()

    for base in base_aliases(wanted, whitelist, extra_aliases):
        expanded.add(base)

        for suffix in QUALITY_SUFFIXES:
            if suffix:
                expanded.add(clean(f"{base} {suffix}"))

    return expanded


def name_matches(channel_name, aliases):
    name = clean(channel_name)

    for alias in aliases:
        if name == alias:
            return True

        if name.startswith(alias + " "):
            remainder = name[len(alias):].strip().split()

            if remainder and all(
                word in ALLOWED_EXTRA_WORDS
                for word in remainder
            ):
                return True

        if name.endswith(" " + alias):
            prefix = name[:-len(alias)].strip().split()

            if prefix and all(
                word in ALLOWED_EXTRA_WORDS
                for word in prefix
            ):
                return True

    return False


def rejected(wanted, channel):
    text = clean(
        channel["name"] + " " +
        channel["info"] + " " +
        channel["url"]
    )

    if any(term in text for term in BAD_REGION_WORDS):
        return True

    for term in SPECIFIC_REJECTS.get(wanted, set()):
        if clean(term) in text:
            return True

    return False


def score(channel, wanted, aliases):
    name = clean(channel["name"])
    text = clean(
        channel["name"] + " " +
        channel["info"] + " " +
        channel["url"]
    )

    points = 0

    wanted_clean = clean(wanted)

    if name == wanted_clean:
        points += 1500

    elif name in aliases:
        points += 1300

    elif name.startswith(wanted_clean + " "):
        points += 1100

    quality_scores = {
        "2160": 180,
        "4k": 180,
        "1080p": 150,
        "1080": 140,
        "fhd": 130,
        "720p": 110,
        "720": 100,
        "hd": 70,
        "576": 40,
        "480": 25,
        "360": 10,
        "hevc": 35,
        "h265": 35,
        "60fps": 25,
        "east": 20,
        "west": 20,
        "usa": 30,
        " us ": 30,
    }

    padded = " " + text + " "

    for term, value in quality_scores.items():
        if term in padded:
            points += value

    source_scores = {
        "manual_overrides": 1000,
        "ota_diginets": 180,
        "iptv_org": 160,
        "iptv-org-category": 150,
        "tablo": 130,
        "samsung": 120,
        "roku_online": 110,
        "tubi": 105,
        "plex": 100,
        "xumo": 95,
        "vizio": 90,
        "free_tv": 85,
        "usa_hanssettings": 70,
    }

    points += source_scores.get(channel["source"], 50)

    return points


whitelist = json.loads(WHITELIST.read_text())

extra_aliases = {}
if ALIASES_FILE.exists():
    extra_aliases = json.loads(ALIASES_FILE.read_text())

bad_urls = set()
for file in BAD_URL_FILES:
    bad_urls |= load_lines(file)

current = current_channel_names()

wanted_channels = []
for group, names in whitelist["categories"].items():
    for wanted in names:
        if wanted not in current:
            wanted_channels.append((group, wanted))

files = []
files += [Path(x) for x in glob.glob("playlists/*.m3u*")]
files += [Path(x) for x in glob.glob("sources/*.m3u*")]
files += [Path(x) for x in glob.glob("scan_cache/*.m3u*")]

files = [
    path for path in files
    if not path.name.lower().startswith("brandentv")
    and path.name not in {"manual_overrides.m3u"}
]

raw = []

for path in files:
    try:
        raw.extend(parse_m3u(path))
    except Exception as exc:
        print(f"SKIP {path}: {exc}")

print("Files scanned:", len(files))
print("Raw channels:", len(raw))
print("Missing whitelist channels:", len(wanted_channels))
print("Hunting...")

results = defaultdict(list)
seen = set()

for group, wanted in wanted_channels:
    aliases = expanded_aliases(
        wanted,
        whitelist,
        extra_aliases,
    )

    for channel in raw:
        if channel["url"] in bad_urls:
            continue

        if not name_matches(channel["name"], aliases):
            continue

        if rejected(wanted, channel):
            continue

        key = (wanted, channel["url"])
        if key in seen:
            continue

        seen.add(key)

        results[wanted].append({
            **channel,
            "group": group,
            "score": score(channel, wanted, aliases),
        })

for wanted in results:
    results[wanted].sort(
        key=lambda item: item["score"],
        reverse=True,
    )

report = []
playlist = ["#EXTM3U"]
json_output = {}

channels_with_candidates = 0
total_candidates = 0

for group, wanted in wanted_channels:
    candidates = results.get(wanted, [])
    json_output[wanted] = candidates

    if not candidates:
        continue

    channels_with_candidates += 1
    total_candidates += len(candidates)

    report.append("=" * 78)
    report.append(
        f"{wanted} | {group} | candidates={len(candidates)}"
    )

    for index, candidate in enumerate(
        candidates[:MAX_PER_CHANNEL],
        1,
    ):
        report.append(
            f"{index:02d}. score={candidate['score']} | "
            f"{candidate['name']} | "
            f"source={candidate['source']}"
        )
        report.append(f"    {candidate['url']}")

        playlist.extend([
            (
                '#EXTINF:-1 '
                'group-title="BrandenTV Hunter",'
                f'{wanted} Candidate {index} - '
                f'{candidate["name"]}'
            ),
            candidate["url"],
        ])

REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
PLAYLIST_OUT.parent.mkdir(parents=True, exist_ok=True)

REPORT_OUT.write_text("\n".join(report) + "\n")
JSON_OUT.write_text(json.dumps(json_output, indent=2) + "\n")
PLAYLIST_OUT.write_text("\n".join(playlist) + "\n")

print()
print("DONE")
print("Missing channels with candidates:", channels_with_candidates)
print("Total candidates:", total_candidates)
print("Report:", REPORT_OUT)
print("JSON:", JSON_OUT)
print("Test playlist:", PLAYLIST_OUT)
