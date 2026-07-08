import json
from pathlib import Path

WL = Path("channel_whitelist.json")
ALIASES = Path("channel_aliases.json")
IDENTITIES = Path("channel_identities.json")

wl = json.load(open(WL))
alias_db = json.load(open(ALIASES))

ids = {}
if IDENTITIES.exists():
    ids = json.load(open(IDENTITIES))

aliases = wl.setdefault("aliases", {})
cats = wl.setdefault("categories", {})
specific_reject = wl.setdefault("specific_reject", {})

# Sync aliases
for channel, names in alias_db.items():
    aliases.setdefault(channel, [])
    for name in names:
        if name not in aliases[channel]:
            aliases[channel].append(name)

# Sync approved identity/variant channels
for channel, info in ids.items():
    category = info.get("category", "Approved Variants")
    parent = info.get("parent")
    reject_from_parent = info.get("reject_from_parent", True)

    cats.setdefault(category, [])
    if channel not in cats[category]:
        cats[category].append(channel)

    aliases.setdefault(channel, [])
    for name in info.get("aliases", []):
        if name not in aliases[channel]:
            aliases[channel].append(name)

    if parent and reject_from_parent:
        specific_reject.setdefault(parent, [])
        for bad in [channel] + info.get("aliases", []):
            if bad not in specific_reject[parent]:
                specific_reject[parent].append(bad)

json.dump(wl, open(WL, "w"), indent=2)
print("Alias Engine synced")
print("Alias channels:", len(alias_db))
print("Identity channels:", len(ids))
