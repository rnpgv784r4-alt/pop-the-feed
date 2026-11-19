import json, re, html, urllib.request, urllib.parse, xml.etree.ElementTree as ET

# (name, home page, [feed addresses to try in order])
SITES = [
 ("Boing Boing", "https://boingboing.net", ["https://boingboing.net/feed"]),
 ("Dangerous Minds", "https://dangerousminds.net", ["https://dangerousminds.net/feed"]),
 ("Phys.org", "https://phys.org", ["https://phys.org/rss-feed/"]),
 ("Atlas Obscura", "https://www.atlasobscura.com", ["https://www.atlasobscura.com/feeds/latest"]),
 ("Colossal", "https://www.thisiscolossal.com", ["https://www.thisiscolossal.com/feed/"]),
 ("Hyperallergic", "https://hyperallergic.com", ["https://hyperallergic.com/feed/"]),
 ("Pitchfork", "https://pitchfork.com", ["https://pitchfork.com/feed/feed-news/rss", "https://pitchfork.com/rss/news/feed/"]),
 ("Post-Punk.com", "https://post-punk.com", ["https://post-punk.com/feed/"]),
 ("Good News Network", "https://www.goodnewsnetwork.org", ["https://www.goodnewsnetwork.org/feed/"]),
 ("Bloody Disgusting", "https://bloody-disgusting.com", ["https://bloody-disgusting.com/feed/"]),
 ("Little White Lies", "https://www.lwlies.com", ["https://www.lwlies.com/feed/"]),
 ("BrooklynVegan", "https://www.brooklynvegan.com", ["https://www.brooklynvegan.com/feed/"]),
 ("It's Nice That", "https://www.itsnicethat.com", ["https://www.itsnicethat.com/rss"]),
 ("Open Culture", "https://www.openculture.com", ["https://www.openculture.com/feed"]),
 ("Biographic", "https://biographic.com", ["https://biographic.com/feed/"]),
 ("Mongabay", "https://news.mongabay.com", ["https://news.mongabay.com/feed/"]),
 ("Smithsonian Ocean", "https://ocean.si.edu", ["https://ocean.si.edu/rss.xml"]),
 ("NASA Earth Observatory", "https://science.nasa.gov/earth/earth-observatory/",
   ["https://science.nasa.gov/earth/earth-observatory/feed/", "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss"]),
 ("Smithsonian History", "https://www.smithsonianmag.com/category/smartnews-history-archaeology/",
   ["https://www.smithsonianmag.com/rss/history/"]),
 ("Audubon", "https://www.audubon.org/magazine", ["https://www.audubon.org/magazine/rss.xml", "https://www.audubon.org/rss.xml"]),
 ("Reader's Digest", "https://www.rd.com", ["https://www.rd.com/feed/"]),
]
PER_FEED = 4
A = "{http://www.w3.org/2005/Atom}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "application/rss+xml, application/xml, text/xml, */*"}
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

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()

def parse_xml(name, data):
    root = ET.fromstring(data)
    out = []
    for it in root.findall(".//item") or root.findall(".//" + A + "entry"):
        title = clean(text(it, "title", A + "title"), 110)
        link = text(it, "link")
        if not link:
            l = it.find(A + "link")
            link = l.get("href") if l is not None else ""
        desc = clean(text(it, "description", A + "summary", A + "content"))
        if title and link.strip().startswith("http"):
            out.append([name, title, desc or "Tap the button below for the full story.", link.strip()])
        if len(out) >= PER_FEED:
            break
    return out

def loose(name, data):
    s = data.decode("utf-8", "ignore")
    out = []
    for blk in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", s, re.S | re.I):
        def f(tag):
            m = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), blk, re.S | re.I)
            return re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)) if m else ""
        title = clean(f("title"), 110)
        link = html.unescape(f("link").strip())
        if not link:
            m = re.search(r"<link[^>]+href=[\"']([^\"']+)", blk, re.I)
            link = html.unescape(m.group(1)) if m else ""
        desc = clean(f("description") or f("summary") or f("content"))
        if title and link.startswith("http"):
            out.append([name, title, desc or "Tap the button below for the full story.", link])
        if len(out) >= PER_FEED:
            break
    return out

def parse(name, data):
    starts = [i for i in (data.find(b"<?xml"), data.find(b"<rss"), data.find(b"<feed")) if i >= 0]
    if starts:
        data = data[min(starts):]
    ends = [data.rfind(t) + len(t) for t in (b"</rss>", b"</feed>") if data.rfind(t) >= 0]
    if ends:
        data = data[:max(ends)]
    try:
        got = parse_xml(name, data)
        if got:
            return got
    except Exception:
        pass
    return loose(name, data)

def discover(home):
    page = get(home).decode("utf-8", "ignore")
    for m in re.finditer(r"<link[^>]+>", page, re.I):
        tag = m.group(0)
        if re.search(r"application/(rss|atom)\+xml", tag, re.I):
            h = re.search(r'href=["\']([^"\']+)', tag)
            if h:
                return [urllib.parse.urljoin(home, html.unescape(h.group(1)))]
    return []

if __name__ == "__main__":
    stories = []
    for name, home, feeds in SITES:
        got = []
        for url in feeds:
            try:
                got = parse(name, get(url))
            except Exception as e:
                print("  try failed", name, url, e)
            if got:
                break
        if not got:
            try:
                for url in discover(home):
                    got = parse(name, get(url))
                    if got:
                        print("  found feed for", name, url)
                        break
            except Exception as e:
                print("  discovery failed", name, e)
        print(name, len(got) if got else "SKIPPED")
        stories += got
    if len(stories) >= 12:
        json.dump(stories, open("stories.json", "w"), ensure_ascii=False, indent=1)
        print("wrote", len(stories))
    else:
        print("too few stories; keeping old file")
