import json
from pathlib import Path
from collections import defaultdict

db=json.load(open("channel_database.json"))
health=json.load(open("stream_health.json")) if Path("stream_health.json").exists() else {}

stats=defaultdict(lambda: {"candidates":0,"ok":0,"used":0,"channels":[]})

healed=json.load(open("healed_overrides.json")) if Path("healed_overrides.json").exists() else {}

for channel, entry in db.items():
    for url,c in entry.get("candidates",{}).items():
        src=c.get("source","unknown")
        stats[src]["candidates"]+=1
        if c.get("last_status") is True or c.get("last_ok") is True:
            stats[src]["ok"]+=1

for channel,h in healed.items():
    if h.get("ok") and h.get("score",0)>0:
        src=h.get("source","unknown")
        stats[src]["used"]+=1
        stats[src]["channels"].append(channel)

lines=[]
lines.append("=============================================")
lines.append("        BrandenTV SOURCE REPORT")
lines.append("=============================================\n")

for src,s in sorted(stats.items(), key=lambda x:(x[1]["used"],x[1]["ok"]), reverse=True):
    total=s["candidates"]
    ok=s["ok"]
    pct=(ok/total*100) if total else 0
    lines.append(f"{src}")
    lines.append(f"  candidates: {total}")
    lines.append(f"  healthy:    {ok} ({pct:.1f}%)")
    lines.append(f"  used:       {s['used']}")
    if s["channels"]:
        lines.append("  winning channels:")
        for ch in sorted(s["channels"])[:25]:
            lines.append(f"    - {ch}")
    lines.append("")

out="docs/source_report.txt"
Path(out).write_text("\n".join(lines),encoding="utf-8")
print("\n".join(lines))
print(f"Wrote {out}")
