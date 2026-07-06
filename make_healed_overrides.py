import json, time
from pathlib import Path
import tvlib

CACHE = Path("candidate_health.json")
OUT = Path("healed_overrides.json")
REPORT = Path("docs/healed_overrides_report.txt")

db = json.load(open("channel_whitelist.json"))
health = json.load(open(CACHE)) if CACHE.exists() else {}
channels = tvlib.load_all_sources()

def resolution(name, info):
    text = (name + " " + info).lower()
    if "4k" in text or "2160" in text: return 2160
    if "1080" in text: return 1080
    if "720" in text: return 720
    if "576" in text: return 576
    if "480" in text: return 480
    return 0

healed = {}
report = []

for group, wanted_list in db["categories"].items():
    for wanted in wanted_list:
        matches = []
        for ch in channels:
            if not tvlib.match_channel(ch, wanted, db):
                continue
            if tvlib.is_rejected(ch, wanted, db):
                continue

            h = health.get(ch["url"], {})
            ok = bool(h.get("ok"))
            sec = float(h.get("seconds", 99))
            res = resolution(ch["name"], ch["info"])

            score = 0
            if ok:
                score += 100000
                score += max(0, 10000 - int(sec * 1000))
            score += res

            if ch["source"] == "manual_overrides":
                score += 5000

            matches.append((score, ok, sec, res, ch))

        matches.sort(key=lambda x: x[0], reverse=True)

        report.append(f"\n=== {wanted} [{group}] ===")

        if not matches:
            report.append("NO CANDIDATES")
            continue

        best = matches[0]
        score, ok, sec, res, ch = best

        healed[wanted] = {
            "group": group,
            "name": wanted,
            "source": ch["source"],
            "raw": ch["name"],
            "url": ch["url"],
            "info": ch["info"],
            "ok": ok,
            "seconds": sec,
            "resolution": res,
            "score": score,
            "alternatives": len(matches),
            "updated": int(time.time())
        }

        report.append(f"WINNER {'OK' if ok else 'BAD'} {sec}s {res}p | {ch['source']} | {ch['name']} | {ch['url']}")

        for score, ok, sec, res, ch in matches[1:6]:
            report.append(f"ALT    {'OK' if ok else 'BAD'} {sec}s {res}p | {ch['source']} | {ch['name']} | {ch['url']}")

OUT.write_text(json.dumps(healed, indent=2), encoding="utf-8")
REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

print(f"Wrote {OUT}")
print(f"Wrote {REPORT}")
print(f"Healed channels: {len(healed)}")
