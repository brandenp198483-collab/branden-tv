import re

BAD_URL_PARTS = [
    "TNT_Novelas",
    "IT_SIMULCAST",
    "AMCCupid",
    "plu-61c0989431084d0007eab12d",
    "206.212.244.63/26",
    "206.212.244.63/674",
]

BAD_REGION_WORDS = [
    "latino","latam","latin america","latinamerica",
    "espanol","español","spanish","mexico","mx",
    "brasil","brazil","argentina","chile","colombia",
    "peru","portugal","italy","russia","india","arabic",
    "korea","japan","novelas","tntnovelas","internacional","panregional","bravotv","bravo tv ar","comedycentralplus"
]

ALIASES = {
    "USA Network": ["usa network", "usa hd", "usa east", "usa"],
    "TBS": ["tbs", "tbs hd", "tbs east"],
    "TLC": ["tlc", "tlc hd", "tlc east"],
    "TNT": ["tnt", "tnt hd", "tnt east"],
    "Bravo": ["bravo", "bravo east", "bravo hd"],
    "Comedy Central": ["comedy central", "comedycentral"],
    "History Channel": ["history channel", "history hd", "history"],
    "Investigation Discovery": ["investigation discovery", "id channel", "discovery id"],
    "Science Channel": ["science channel", "discovery science"],
    "Animal Planet": ["animal planet"],
    "Cooking Channel": ["cooking channel"],
    "Cartoon Network": ["cartoon network"],
    "Adult Swim": ["adult swim"],
    "Boomerang": ["boomerang"],
    "TruTV": ["trutv", "tru tv"],
    "GSN": ["gsn", "game show network"],
    "LMN": ["lmn", "lifetime movie network", "lifetime movies"],
}

def clean(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "

def looks_bad_region(text):
    raw = str(text)
    c = clean(text)

    if any(x.lower() in raw.lower() for x in BAD_URL_PARTS):
        return True

    if "tnt novelas" in c or "tntnovelas" in c:
        return True

    if "amc cupid" in c or "amccupid" in c:
        return True

    if "tvg country it" in c or "country it" in c:
        return True

    return any(f" {w} " in c for w in BAD_REGION_WORDS)

def aliases_for(wanted):
    return ALIASES.get(wanted, [wanted])

def smart_score(wanted, candidate_text):
    c = clean(candidate_text)
    score = 0

    for alias in aliases_for(wanted):
        a = clean(alias)
        if a.strip() and a in c:
            score += 500

    if looks_bad_region(candidate_text):
        score -= 1000

    if " hd " in c or " 1080 " in c or " 720 " in c:
        score += 40
    if " east " in c or " us " in c or " usa " in c or " united states " in c:
        score += 80

    return score

def is_match(wanted, candidate_text, minimum=300):
    return smart_score(wanted, candidate_text) >= minimum


def reject_for_channel(wanted, ch):
    if isinstance(ch, dict):
        text = " ".join(str(ch.get(k, "")) for k in ("name", "raw", "info", "url", "group", "source")).lower()
    else:
        text = str(ch).lower()

    rejects = {
        "TNT": ["novelas", "tnt novelas"],
        "AMC": ["amc cupid", "amc reality"],
        "Bravo": ["bravo tv", "bravotv", "bravo latin", "bravo latino"],
        "AccuWeather Network": ["samaya", "hindi", "india"],
        "Discovery Channel": [".it", "italy", "italia", "it_simulcast", "latino", "espanol", "español", "spanish", "dubbed"],
        "Comedy Central": ["pluto", "latino", "espanol", "español", ".ro@", "romania", "romanian"],
    }

    return any(bad in text for bad in rejects.get(wanted, []))


BAD_URL_BITS = [
    "amc-cupid","amccupid","amc_reality","amc reality",
    "tntnovelas","tnt_novelas","novelas",
    "usa_lmn","/lmn/","lifetime movies",
    "mtvbiggestpop","mtv_biggest_pop","biggest pop",
    "espn-vivo","espn_vivo","vivo",
    "latino","espanol","español","french","france","italy","italia",
    "arabic","samaya","hindi","india",
]

def global_bad_stream(ch):
    text = " ".join(str(ch.get(k,"")) for k in ("name","raw","info","url","group","source")).lower() if isinstance(ch,dict) else str(ch).lower()
    return any(x in text for x in BAD_URL_BITS)

