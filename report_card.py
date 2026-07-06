import json
from pathlib import Path
from collections import defaultdict

OUT = Path("docs/report_card.txt")

whitelist=json.load(open("channel_whitelist.json"))
db=json.load(open("channel_database.json")) if Path("channel_database.json").exists() else {}
health=json.load(open("stream_health.json")) if Path("stream_health.json").exists() else {}

wanted=sum(len(v) for v in whitelist["categories"].values())
found=sum(1 for ch in db.values() if ch.get("candidates"))
healthy=sum(1 for x in health.values() if x.get("ok"))
bad=sum(1 for x in health.values() if not x.get("ok"))

sources=defaultdict(lambda: {"candidates":0,"successes":0,"failures":0})
for ch in db.values():
    for c in ch.get("candidates", {}).values():
        s=sources[c.get("source","unknown")]
        s["candidates"]+=1
        s["successes"]+=c.get("successes",0)
        s["failures"]+=c.get("failures",0)

lines=[]
lines.append("="*45)
lines.append("        BrandenTV REPORT CARD")
lines.append("="*45)
lines.append(f"Whitelist channels:       {wanted}")
lines.append(f"Channels with candidates: {found}")
lines.append(f"Final healthy streams:    {healthy}")
lines.append(f"Final bad streams:        {bad}")
lines.append("")

lines.append("SOURCE GRADES:")
for name,s in sorted(sources.items()):
    total=s["successes"]+s["failures"]
    pct=(s["successes"]/total*100) if total else 0
    lines.append(f"- {name}: candidates={s['candidates']} health={pct:.1f}%")

lines.append("")
lines.append("MISSING / NO CANDIDATES:")
for name,ch in db.items():
    if not ch.get("candidates"):
        lines.append(f"- {name}")

lines.append("")
lines.append("BROKEN FINAL LINEUP:")
for url,x in health.items():
    if not x.get("ok"):
        lines.append(f"- {x.get('channel')} ({x.get('seconds')}s)")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(lines)+"\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nWrote {OUT}")
