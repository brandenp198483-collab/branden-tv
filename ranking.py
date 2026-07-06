def uptime(c):
    s = c.get("successes", 0)
    f = c.get("failures", 0)
    t = s + f
    return (s / t) if t else 0

def source_grades(db):
    stats = {}
    for entry in db.values():
        for c in entry.get("candidates", {}).values():
            src = c.get("source", "unknown")
            stats.setdefault(src, {"s": 0, "f": 0})
            stats[src]["s"] += c.get("successes", 0)
            stats[src]["f"] += c.get("failures", 0)

    grades = {}
    for src, x in stats.items():
        total = x["s"] + x["f"]
        grades[src] = (x["s"] / total) if total else 0
    return grades

def score_candidate(c, source_grade=0):
    score = 0

    currently_ok = c.get("last_status") is True

    if currently_ok:
        score += 3000
    else:
        score -= 5000

    score += int(uptime(c) * 3000)

    res = c.get("resolution", 0)
    if res >= 2160: score += 900
    elif res >= 1080: score += 700
    elif res >= 720: score += 450
    elif res >= 480: score += 200

    sec = c.get("last_seconds")
    if sec is not None:
        score += max(0, 1000 - int(float(sec) * 300))

    if c.get("url", "").startswith("https://"):
        score += 150

    info = (c.get("info", "") or "").lower()
    if "tvg-logo=" in info and 'tvg-logo=""' not in info:
        score += 250
    if "tvg-id=" in info and 'tvg-id=""' not in info:
        score += 250

    score += int(source_grade * 750)
    score -= c.get("failures", 0) * 100

    return score

def best_candidate(candidates, source_grade_map=None):
    source_grade_map = source_grade_map or {}
    ranked = []

    for url, c in candidates.items():
        sg = source_grade_map.get(c.get("source", ""), 0)
        ranked.append((score_candidate(c, sg), url, c))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked
