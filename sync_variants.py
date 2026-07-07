import json
from pathlib import Path

wl_path = Path("channel_whitelist.json")
var_path = Path("channel_variants.json")

wl = json.load(open(wl_path))
variants = json.load(open(var_path))

cats = wl.setdefault("categories", {})
aliases = wl.setdefault("aliases", {})
specific_reject = wl.setdefault("specific_reject", {})

for variant, info in variants.items():
    parent = info.get("parent")
    category = info.get("category", "Approved Variants")
    names = info.get("aliases", [])

    # Add variant as its own real channel
    cats.setdefault(category, [])
    if variant not in cats[category]:
        cats[category].append(variant)

    # Add aliases for variant
    aliases.setdefault(variant, [])
    for name in names:
        if name not in aliases[variant]:
            aliases[variant].append(name)

    # Stop variant from satisfying parent channel
    if parent:
        specific_reject.setdefault(parent, [])
        for name in [variant] + names:
            if name not in specific_reject[parent]:
                specific_reject[parent].append(name)

json.dump(wl, open(wl_path, "w"), indent=2)
print("Synced approved channel variants")
