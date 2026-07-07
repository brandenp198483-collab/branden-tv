import json
from pathlib import Path

wl_path = Path("channel_whitelist.json")
identity_path = Path("channel_identities.json")

wl = json.load(open(wl_path))
ids = json.load(open(identity_path))

cats = wl.setdefault("categories", {})
aliases = wl.setdefault("aliases", {})
specific_reject = wl.setdefault("specific_reject", {})

for channel, info in ids.items():
    parent = info.get("parent")
    category = info.get("category", "Approved Variants")
    names = info.get("aliases", [])

    cats.setdefault(category, [])
    if channel not in cats[category]:
        cats[category].append(channel)

    aliases.setdefault(channel, [])
    for name in names:
        if name not in aliases[channel]:
            aliases[channel].append(name)

    if parent and info.get("reject_from_parent", True):
        specific_reject.setdefault(parent, [])
        for name in [channel] + names:
            if name not in specific_reject[parent]:
                specific_reject[parent].append(name)

json.dump(wl, open(wl_path, "w"), indent=2)
print("Synced channel identities")
