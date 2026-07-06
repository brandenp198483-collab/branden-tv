def uptime(c):
    s=c.get("successes",0)
    f=c.get("failures",0)
    t=s+f
    return (s/t) if t else 0

def score_candidate(c, source_grade=0):
    score=0

    up=uptime(c)
    score += int(up * 5000)

    res=c.get("resolution",0)
    if res >= 2160: score += 900
    elif res >= 1080: score += 700
    elif res >= 720: score += 450
    elif res >= 480: score += 200

    sec=c.get("last_seconds")
    if sec is not None:
        score += max(0, 1000 - int(float(sec)*300))

    if c.get("last_ok"):
        score += 1000
    else:
        score -= 5000

    if c.get("url","").startswith("https://"):
        score += 150

    info=(c.get("info","") or "").lower()
    if "tvg-logo=" in info and 'tvg-logo=""' not in info:
        score += 250
    if "tvg-id=" in info and 'tvg-id=""' not in info:
        score += 250

    score += int(source_grade * 500)

    score -= c.get("failures",0) * 150

    return score

def best_candidate(candidates, source_grades=None):
    source_grades = source_grades or {}
    ranked=[]
    for url,c in candidates.items():
        sg=source_grades.get(c.get("source",""),0)
        ranked.append((score_candidate(c, sg), url, c))
    ranked.sort(key=lambda x:x[0], reverse=True)
    return ranked
