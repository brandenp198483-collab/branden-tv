import subprocess, sys, json
from pathlib import Path

def run(name, cmd):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"FAILED: {name}")
        sys.exit(result.returncode)

def guard_verify():
    p = Path("stream_health.json")
    if not p.exists():
        return

    data = json.load(open(p))
    total = len(data)
    bad = sum(1 for x in data.values() if not x.get("ok"))

    if total >= 20 and bad / total >= 0.80:
        print()
        print("🚨 SAFETY STOP")
        print(f"{bad}/{total} streams failed.")
        print("This looks like bad internet/DNS, not bad streams.")
        print("Do NOT commit this run.")
        sys.exit(99)

steps = [
    ("Update database", ["python", "update_database.py"]),
    ("Test candidates", ["python", "heal_candidates.py"]),
    ("Make healed overrides", ["python", "make_healed_overrides.py"]),
    ("Build playlist", ["python", "build_playlist.py"]),
    ("Verify final lineup", ["python", "verify_streams.py"]),
]

for name, cmd in steps:
    run(name, cmd)

guard_verify()

run("Generate report card", ["python", "report_card.py"])
run("Generate source report", ["python", "source_report.py"])
run("Build EPG", ["python", "build_epg.py"])

print()
print("DONE - BrandenTV update complete")
