import json, re, html, urllib.request, xml.etree.ElementTree as ET
FEEDS = [
 ("Boing Boing", "https://boingboing.net/feed"),
 ("Dangerous Minds", "https://dangerousminds.net/feed"),
 ("Phys.org", "https://phys.org/rss-feed/"),
 ("Atlas Obscura", "https://www.atlasobscura.com/feeds/latest"),
 ("Colossal", "https://www.thisiscolossal.com/feed/"),
 ("Hyperallergic", "https://hyperallergic.com/feed/"),
 ("Aquarium Drunkard", "https://aquariumdrunkard.com/feed/"),
 ("Post-Punk.com", "https://post-punk.com/feed/"),
 ("Good News Network", "https://www.goodnewsnetwork.org/feed/"),
]
PER_FEED = 4
A = "{http://www.w3.org/2005/Atom}"

JUNK = re.compile(r"appeared first on|member|reader-supported|matter to you|support (independent|our)|subscribe|newsletter|sign up", re.I)

def clean(s, n=190):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    s = " ".join(p for p in re.split(r"(?<=[.!?])\s+", s) if not JUNK.search(p))
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s

def text(e, *names):
    for n in names:
        x = e.find(n)
        if x is not None and (x.text or "").strip():
            return x.text
    return ""

stories = []
for name, url in FEEDS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PopTheFeed/1.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=25).read())
        items = root.findall(".//item") or root.findall(".//" + A + "entry")
        got = 0
        for it in items:
            title = clean(text(it, "title", A + "title"), 110)
            link = text(it, "link")
            if not link:
                l = it.find(A + "link")
                link = l.get("href") if l is not None else ""
            desc = clean(text(it, "description", A + "summary", A + "content"))
            if title and link.startswith("http"):
                stories.append([name, title, desc or "Tap the button below for the full story.", link.strip()])
                got += 1
            if got >= PER_FEED:
                break
        print(name, got)
    except Exception as e:
        print("SKIPPED", name, e)

if len(stories) >= 12:
    json.dump(stories, open("stories.json", "w"), ensure_ascii=False, indent=1)
    print("wrote", len(stories))
else:
    print("too few stories; keeping old file")
