import glob
import json
import re
import requests
from collections import defaultdict
from pathlib import Path

from channel_matcher import reject_for_channel

WHITELIST_FILE = Path("channel_whitelist.json")
ALIASES_FILE = Path("config/channel_aliases.json")
BAD_URL_FILES = [
    Path("config/bad_urls.txt"),
    Path("bad_urls.txt"),
    Path("playlists/bad_urls.txt"),
]
OUT_FILE = Path("docs/broad_usa_scan.txt")
JSON_OUT = Path("broad_usa_candidates.json")

QUALITY_WORDS = {
    "us", "usa", "united states", "east", "west", "national",
    "hd", "fhd", "uhd", "sd", "4k", "2160", "1080", "1080p",
    "720", "720p", "576", "480", "360", "360p",
    "h265", "hevc", "x265", "60fps", "vip", "backup",
    "auto", "main", "premium", "live", "channel", "network",
}

BAD_REGION_WORDS = {
    "latin america", "latino", "latina", "espanol", "español",
    "mexico", "méxico", "brasil", "brazil", "portugal",
    "arabic", "arabia", "india", "pakistan", "africa",
    "asia", "korea", "japan", "turkey", "turkiye",
}

def clean(text):
    text = text.lower()
    text = text.replace("&", " and ")
    text = text.replace("+", " plus ")
    text = text.replace("🇺🇸", " usa ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()

def compact(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower().replace("&", "and"))

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
    results = []

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

                # Some imported playlists append the display name after
                # an HLS/TS URL, for example:
                # https://example.com/playlist.m3u8:Channel Name
                for marker in [".m3u8:", ".mpd:", ".ts:"]:
                    pos = url.lower().find(marker)
                    if pos != -1:
                        url = url[:pos + len(marker) - 1]
                        break

                break
            if nxt.startswith("#EXTINF"):
                break

        if url:
            # Some HansSettings-style lines append ":Channel Name"
            # directly after the real URL.
            suffix = ":" + name
            if url.lower().endswith(suffix.lower()):
                url = url[:-len(suffix)]

            results.append({
                "name": name,
                "info": info,
                "url": url,
                "source": path.stem,
                "file": str(path),
            })

    return results

def alias_forms(alias):
    base = clean(alias)
    forms = {base}

    # Common punctuation and abbreviation normalization.
    forms.add(clean(alias.replace("&", "and")))
    forms.add(clean(alias.replace("&", "")))

    # Remove quality/provider suffixes to create the true channel base.
    words = base.split()
    while words and words[-1] in QUALITY_WORDS:
        words.pop()

    if words:
        forms.add(" ".join(words))

    return {x for x in forms if x}

def plausible_match(channel_name, alias_set):
    cname = clean(channel_name)
    ccompact = compact(channel_name)

    for alias in alias_set:
        a = clean(alias)
        if not a:
            continue

        acompact = compact(alias)

        if cname == a or ccompact == acompact:
            return True

        # Provider prefixes: US | Discovery Channel, USA: A&E HD.
        if cname.endswith(" " + a) or cname.startswith(a + " "):
            extras = cname.replace(a, " ", 1).split()
            if all(x in QUALITY_WORDS for x in extras):
                return True

        # Exact channel plus only recognized quality/provider tokens.
        if cname.startswith(a + " "):
            remainder = cname[len(a):].strip().split()
            if remainder and all(x in QUALITY_WORDS for x in remainder):
                return True

    return False

db = json.loads(WHITELIST_FILE.read_text())
extra_aliases = (
    json.loads(ALIASES_FILE.read_text())
    if ALIASES_FILE.exists()
    else {}
)

bad_urls = set()
for path in BAD_URL_FILES:
    bad_urls |= load_lines(path)

wanted_channels = []
for group, names in db["categories"].items():
    for wanted in names:
        wanted_channels.append((group, wanted))

aliases_by_channel = {}

for _, wanted in wanted_channels:
    aliases = {wanted}
    aliases.update(db.get("aliases", {}).get(wanted, []))
    aliases.update(extra_aliases.get(wanted, []))

    expanded = set()
    for alias in aliases:
        expanded.update(alias_forms(alias))

    aliases_by_channel[wanted] = sorted(expanded)

files = []
files += [Path(x) for x in glob.glob("playlists/*.m3u*")]
files += [Path(x) for x in glob.glob("sources/*.m3u*")]

# Do not scan generated BrandenTV output files back into the candidate pool.
files = [
    p for p in files
    if not p.name.lower().startswith("brandentv")
    and p.name not in {
        "manual_overrides.m3u",
        "bad_urls.txt",
    }
]

raw = []

# Scan local source files.
for path in files:
    try:
        raw.extend(parse_m3u(path))
    except Exception as exc:
        print(f"SKIP local {path}: {exc}")

local_count = len(raw)

# Download and scan every configured remote source.
remote_sources = json.loads(Path("sources.json").read_text())
cache_dir = Path("scan_cache")
cache_dir.mkdir(exist_ok=True)

remote_ok = 0
remote_failed = 0

for source_name, source_url in remote_sources.items():
    print(f"Downloading remote scan source: {source_name}")

    try:
        response = requests.get(
            source_url,
            timeout=40,
            headers={"User-Agent": "BrandenTV-Scanner/1.0"},
        )
        response.raise_for_status()

        cache_file = cache_dir / f"{source_name}.m3u"
        cache_file.write_text(response.text, errors="ignore")

        channels = parse_m3u(cache_file)

        # Preserve the real configured source name.
        for channel in channels:
            channel["source"] = source_name
            channel["file"] = source_url

        raw.extend(channels)
        remote_ok += 1

    except Exception as exc:
        remote_failed += 1
        print(f"FAILED remote {source_name}: {exc}")

print("Local source files:", len(files))
print("Raw local channels:", local_count)
print("Remote sources downloaded:", remote_ok)
print("Remote sources failed:", remote_failed)
print("Combined raw channels:", len(raw))
print("Whitelist channels:", len(wanted_channels))
print("Scanning...")

matches = defaultdict(list)
seen = set()

for ch in raw:
    if ch["url"] in bad_urls:
        continue

    combined = f'{ch["name"]} {ch["info"]} {ch["url"]}'
    low = clean(combined)

    for group, wanted in wanted_channels:
        aliases = aliases_by_channel[wanted]

        if not plausible_match(ch["name"], aliases):
            continue

        if reject_for_channel(wanted, combined):
            continue

        allowed_spanish = {
            clean(x) for x in db.get("spanish_allowed", [])
        }

        if clean(wanted) not in allowed_spanish:
            if any(clean(x) in low for x in BAD_REGION_WORDS):
                continue

        key = (wanted, ch["url"])
        if key in seen:
            continue
        seen.add(key)

        matches[wanted].append({
            **ch,
            "group": group,
        })

lines = []
json_data = {}

for group, wanted in wanted_channels:
    found = matches.get(wanted, [])
    json_data[wanted] = found

    lines.append("=" * 78)
    lines.append(f"{wanted} | {group} | candidates={len(found)}")

    if not found:
        lines.append("MISS")
        continue

    for idx, ch in enumerate(found[:50], 1):
        lines.append(
            f"{idx:02d}. {ch['name']} | source={ch['source']}"
        )
        lines.append(f"    file={ch['file']}")
        lines.append(f"    {ch['url']}")

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
OUT_FILE.write_text("\n".join(lines) + "\n")
JSON_OUT.write_text(json.dumps(json_data, indent=2) + "\n")

channels_with_matches = sum(bool(v) for v in matches.values())
candidate_count = sum(len(v) for v in matches.values())

print()
print("DONE")
print("Channels with broad matches:", channels_with_matches)
print("Total broad candidates:", candidate_count)
print("Text report:", OUT_FILE)
print("JSON database:", JSON_OUT)
