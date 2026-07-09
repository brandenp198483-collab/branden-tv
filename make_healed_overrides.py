from channel_matcher import reject_for_channel
from channel_matcher import looks_bad_region
import json, time
from pathlib import Path
import ranking

DB_FILE = Path("channel_database.json")
OUT = Path("healed_overrides.json")
REPORT = Path("docs/healed_overrides_report.txt")

whitelist = json.load(open("channel_whitelist.json"))
db = json.load(open(DB_FILE))
source_grade_map = ranking.source_grades(db)

healed = {}
report = []
now = int(time.time())

for group, names in whitelist["categories"].items():
    for wanted in names:
        entry = db.get(wanted, {"candidates": {}})
        candidates = entry.get("candidates", {})

        # Apply channel-specific reject rules even to remembered database candidates
        rejects = [x.lower() for x in whitelist.get("specific_reject", {}).get(wanted, [])]
        filtered = {}
        for url, c in candidates.items():
            haystack = " ".join([
                str(c.get("raw", "")),
                str(c.get("info", "")),
                str(c.get("url", "")),
            ]).lower()
            if any(bad in haystack for bad in rejects):
                continue
            filtered[url] = c

        filtered = {
            url: c for url, c in filtered.items()
            if not reject_for_channel(wanted, c)
        }

        ranked = ranking.best_candidate(filtered, source_grade_map)

        report.append(f"\n=== {wanted} [{group}] ===")

        if not ranked:
            report.append("NO CANDIDATES")
            continue

        best_score, best_url, best = ranked[0]

        healed[wanted] = {
            "group": group,
            "name": wanted,
            "source": best.get("source"),
            "raw": best.get("raw"),
            "url": best.get("url"),
            "info": best.get("info"),
            "ok": best.get("last_status") is True,
            "seconds": best.get("last_seconds"),
            "resolution": best.get("resolution", 0),
            "score": best_score,
            "alternatives": len(ranked),
            "updated": now
        }

        report.append(
            f"WINNER {'OK' if best.get('last_status') is True else 'BAD'} "
            f"score={best_score} {best.get('last_seconds')}s {best.get('resolution',0)}p | "
            f"{best.get('source')} | {best.get('raw')} | {best.get('url')}"
        )

        for score, url, c in ranked[1:6]:
            report.append(
                f"ALT    {'OK' if c.get('last_status') is True else 'BAD'} "
                f"score={score} {c.get('last_seconds')}s {c.get('resolution',0)}p | "
                f"{c.get('source')} | {c.get('raw')} | {url}"
            )

OUT.write_text(json.dumps(healed, indent=2), encoding="utf-8")
REPORT.parent.mkdir(exist_ok=True)
REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

print(f"Wrote {OUT}")
print(f"Wrote {REPORT}")
print(f"Healed channels: {len(healed)}")
