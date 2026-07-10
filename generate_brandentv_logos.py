import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAP_FILE = Path("config/channel_logos.json")
LOGO_DIR = Path("docs/logos")
SIZE = 512

LOGO_DIR.mkdir(parents=True, exist_ok=True)
logo_map = json.loads(MAP_FILE.read_text())

FONT_CANDIDATES = [
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/system/fonts/Roboto-Bold.ttf",
    "/system/fonts/Roboto-Medium.ttf",
]

REGULAR_FONT_CANDIDATES = [
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/system/fonts/Roboto-Regular.ttf",
]

def find_font(candidates):
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None

BOLD_FONT = find_font(FONT_CANDIDATES)
REGULAR_FONT = find_font(REGULAR_FONT_CANDIDATES) or BOLD_FONT

def font(size, bold=True):
    path = BOLD_FONT if bold else REGULAR_FONT
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def initials(name):
    special = {
        "The CW": "CW",
        "The Weather Channel": "TWC",
        "USA Network": "USA",
        "MLB Network": "MLB",
        "MLB Network Strike Zone": "MLB SZ",
        "ION Television": "ION",
        "History Channel": "HIST",
        "BYU TV": "BYU",
        "MeTV": "MeTV",
        "MeTV+": "MeTV+",
        "MeTV Toons": "MeTV",
        "A&E": "A&E",
        "BBC America": "BBC",
        "BBC World News": "BBC",
        "CBS Sports Network": "CBS",
        "Investigation Discovery": "ID",
        "National Geographic": "NAT GEO",
        "Nat Geo Wild": "NAT GEO",
        "Fox Sports 1": "FS1",
        "Fox Sports 2": "FS2",
        "Big Ten Network": "BTN",
        "ACC Network": "ACCN",
        "SEC Network": "SECN",
        "NFL Network": "NFL",
        "NBA TV": "NBA",
        "NHL Network": "NHL",
        "PBS Kids": "PBS",
    }

    if name in special:
        return special[name]

    words = re.findall(r"[A-Za-z0-9]+", name)

    if len(name) <= 9:
        return name.upper()

    if len(words) == 1:
        return words[0][:8].upper()

    return "".join(word[0] for word in words[:5]).upper()

def fit_font(draw, text, max_width, start_size, min_size=18, bold=True):
    size = start_size

    while size >= min_size:
        fnt = font(size, bold=bold)
        box = draw.textbbox((0, 0), text, font=fnt)
        width = box[2] - box[0]

        if width <= max_width:
            return fnt

        size -= 2

    return font(min_size, bold=bold)

def draw_centered(draw, xy, text, fnt, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    width = box[2] - box[0]
    height = box[3] - box[1]

    x = xy[0] - width / 2
    y = xy[1] - height / 2 - box[1]

    draw.text((x, y), text, font=fnt, fill=fill)

created = 0
failed = 0

for channel, filename in logo_map.items():
    try:
        image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # BrandenTV-style dark rounded card.
        draw.rounded_rectangle(
            (24, 24, 488, 488),
            radius=58,
            fill=(20, 22, 30, 255),
            outline=(245, 197, 24, 255),
            width=10,
        )

        # Accent bar.
        draw.rounded_rectangle(
            (58, 62, 454, 78),
            radius=8,
            fill=(245, 197, 24, 255),
        )

        short = initials(channel)

        short_font = fit_font(
            draw,
            short,
            max_width=390,
            start_size=104,
            min_size=48,
            bold=True,
        )

        name_font = fit_font(
            draw,
            channel,
            max_width=390,
            start_size=34,
            min_size=20,
            bold=True,
        )

        brand_font = font(21, bold=False)

        draw_centered(
            draw,
            (256, 220),
            short,
            short_font,
            (255, 255, 255, 255),
        )

        draw_centered(
            draw,
            (256, 340),
            channel,
            name_font,
            (245, 197, 24, 255),
        )

        draw_centered(
            draw,
            (256, 426),
            "BRANDENTV",
            brand_font,
            (180, 184, 198, 255),
        )

        output = LOGO_DIR / filename
        image.save(output, "PNG", optimize=True)

        created += 1

    except Exception as exc:
        failed += 1
        print(f"FAILED: {channel}: {exc}")

print("Created:", created)
print("Failed:", failed)
print("Folder:", LOGO_DIR)
