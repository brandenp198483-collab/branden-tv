import subprocess, sys

steps = [
    ("Update database", ["python", "update_database.py"]),
    ("Test candidates", ["python", "heal_candidates.py"]),
    ("Make healed overrides", ["python", "make_healed_overrides.py"]),
    ("Build playlist", ["python", "build_playlist.py"]),
    ("Verify final lineup", ["python", "verify_streams.py"]),
    ("Generate report card", ["python", "report_card.py"]),
]

for name, cmd in steps:
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"FAILED: {name}")
        sys.exit(result.returncode)

print()
print("DONE - BrandenTV update complete")
