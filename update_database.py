import json, time
from pathlib import Path
import tvlib

DB_FILE = Path("channel_database.json")
REPORT = Path("docs/channel_database_report.txt")

def res_score(name, info):
    t=(name+" "+info).lower()
    if "2160" in t or "4k" in t: return 2160
    if "1080" in t: return 1080
    if "720" in t: return 720
    if "576" in t: return 576
    if "480" in t: return 480
    return 0

whitelist=json.load(open("channel_whitelist.json"))
old=json.load(open(DB_FILE)) if DB_FILE.exists() else {}
sources=tvlib.load_all_sources()
now=int(time.time())

db={}
report=[]

for group,names in whitelist["categories"].items():
    for wanted in names:
        key=wanted
        db[key]=old.get(key, {"group":group,"name":wanted,"candidates":{}})
        db[key]["group"]=group
        db[key]["name"]=wanted

        found=0
        for ch in sources:
            if not tvlib.match_channel(ch,wanted,whitelist): continue
            if tvlib.is_rejected(ch,wanted,whitelist): continue

            url=ch["url"]
            c=db[key]["candidates"].get(url,{})
            c.update({
                "url":url,
                "source":ch["source"],
                "raw":ch["name"],
                "info":ch["info"],
                "resolution":res_score(ch["name"],ch["info"]),
                "last_seen":now,
            })
            c.setdefault("successes",0)
            c.setdefault("failures",0)
            c.setdefault("last_ok",None)
            c.setdefault("last_seconds",None)
            db[key]["candidates"][url]=c
            found+=1

        report.append(f"{wanted}: {found} candidates")

DB_FILE.write_text(json.dumps(db,indent=2),encoding="utf-8")
REPORT.parent.mkdir(exist_ok=True)
REPORT.write_text("\n".join(report)+"\n",encoding="utf-8")

print(f"Wrote {DB_FILE}")
print(f"Wrote {REPORT}")
print(f"Channels: {len(db)}")
