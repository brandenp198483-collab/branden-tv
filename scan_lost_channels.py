import json, re
from pathlib import Path

NEEDLES = {
    "USA Network": ["usa network", "usa hd", "usa east", " usa "],
    "TBS": ["tbs", "tbs hd", "tbs east"],
    "TLC": ["tlc", "tlc hd"],
    "History Channel": ["history", "history channel"],
    "Investigation Discovery": ["investigation discovery", "id channel", "discovery id"],
    "Science Channel": ["science channel", "discovery science"],
    "Animal Planet": ["animal planet"],
    "Cooking Channel": ["cooking channel"],
    "Cartoon Network": ["cartoon network"],
    "Adult Swim": ["adult swim"],
    "Boomerang": ["boomerang"],
    "TruTV": ["trutv", "tru tv"],
    "GSN": ["gsn", "game show"],
    "LMN": ["lmn", "lifetime movies"],
}

BAD = ["brasil","brazil","latam","latin","mx","mexico","espanol","español","india","russia","korea","japan"]

def clean(s):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip() + " "

def walk(x):
    if isinstance(x, dict):
        if any(k in x for k in ("url","name","raw","title","source")):
            yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)

db = json.loads(Path("channel_database.json").read_text(errors="ignore"))
rows = list(walk(db))

out=[]
for wanted, needles in NEEDLES.items():
    out += ["="*70, wanted, "="*70]
    found=0
    for r in rows:
        blob = clean(" ".join(str(r.get(k,"")) for k in r.keys()))
        if any(n in blob for n in needles):
            found += 1
            bad = "BAD_REGION?" if any(b in blob for b in BAD) else "POSSIBLE"
            out.append(f'{found:02d}. {bad} | {r.get("source","")} | {r.get("name") or r.get("title") or r.get("raw","")}')
            out.append(f'    {r.get("url","")}')
    if not found:
        out.append("NO SOURCE MATCHES")

Path("docs/lost_channel_scan.txt").write_text("\n".join(out)+"\n")
print("Scanned rows:", len(rows))
print("Wrote docs/lost_channel_scan.txt")
