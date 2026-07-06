import json, time
from pathlib import Path
import tvlib
import ranking

CACHE = Path("candidate_health.json")
OUT = Path("healed_overrides.json")
REPORT = Path("docs/healed_overrides_report.txt")

db = json.load(open("channel_whitelist.json"))
health = json.load(open(CACHE)) if CACHE.exists() else {}
channels = tvlib.load_all_sources()

healed = {}

report = []

for group, wanted_list in db["categories"].items():
    for wanted in wanted_list:
        matches = []
        db_entry = json.load(open("channel_database.json")).get(wanted, {"candidates": {}})
        for ch in channels:
            if not tvlib.match_channel(ch, wanted, db):
                continue
            if tvlib.is_rejected(ch, wanted, db):
                continue

            c = db_entry["candidates"].get(ch["url"], {})
            ok = bool(c.get("last_ok"))
            sec = float(c.get("last_seconds", 99) or 99)
            res = c.get("resolution", 0)
            score = ranking.score_candidate(c)

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
