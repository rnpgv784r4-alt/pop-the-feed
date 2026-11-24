import json, re, html, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import time, base64

# (name, home page, [feed addresses to try in order], category)
# Categories must be exactly: Art, Entertainment, Oddities, History, Science
SITES = [
 ("Boing Boing", "https://boingboing.net", ["https://boingboing.net/feed"], "Oddities"),
 ("Kottke", "https://kottke.org", ["https://feeds.kottke.org/main"], "Oddities"),
 ("Atlas Obscura", "https://www.atlasobscura.com", ["https://www.atlasobscura.com/feeds/latest"], "Oddities"),
 ("Good News Network", "https://www.goodnewsnetwork.org", ["https://www.goodnewsnetwork.org/feed/"], "Oddities"),
 ("Reader's Digest", "https://www.rd.com", ["https://www.rd.com/feed/"], "Oddities"),

 ("Louder Than War", "https://louderthanwar.com", ["https://louderthanwar.com/feed/"], "Entertainment"),
 ("Bandcamp Daily", "https://daily.bandcamp.com", ["https://daily.bandcamp.com/feed"], "Entertainment"),
 ("Dangerous Minds", "https://dangerousminds.net", ["https://dangerousminds.net/feed"], "Entertainment"),
 ("Pitchfork", "https://pitchfork.com", ["https://pitchfork.com/feed/feed-news/rss", "https://pitchfork.com/rss/news/feed/"], "Entertainment"),
 ("Post-Punk.com", "https://post-punk.com", ["https://post-punk.com/feed/"], "Entertainment"),
 ("Bloody Disgusting", "https://bloody-disgusting.com", ["https://bloody-disgusting.com/feed/"], "Entertainment"),
 ("Little White Lies", "https://www.lwlies.com", ["https://www.lwlies.com/feed/"], "Entertainment"),
 ("BrooklynVegan", "https://www.brooklynvegan.com", ["https://www.brooklynvegan.com/feed/"], "Entertainment"),

 ("Beautiful Bizarre Magazine", "https://beautifulbizarre.net", ["https://beautifulbizarre.net/feed/"], "Art"),
 ("StreetArtNews", "https://streetartnews.net", ["https://streetartnews.net/feed"], "Art"),
 ("GraffitiStreet", "https://graffitistreet.com", ["https://graffitistreet.com/feed/"], "Art"),
 ("Sour Harvest", "https://www.sourharvest.com", ["https://www.sourharvest.com/feed/"], "Art"),
 ("DailyArt Magazine", "https://www.dailyartmagazine.com", ["https://www.dailyartmagazine.com/feed/"], "Art"),
 ("Creative Boom", "https://www.creativeboom.com", ["https://www.creativeboom.com/feed/"], "Art"),
 ("Colossal", "https://www.thisiscolossal.com", ["https://www.thisiscolossal.com/feed/"], "Art"),
 ("Hyperallergic", "https://hyperallergic.com", ["https://hyperallergic.com/feed/"], "Art"),
 ("It's Nice That", "https://www.itsnicethat.com", ["https://www.itsnicethat.com/rss"], "Art"),

 ("Please Kill Me", "https://pleasekillme.com", ["https://pleasekillme.com/feed/"], "History"),
 ("The Public Domain Review", "https://publicdomainreview.org", ["https://publicdomainreview.org/rss.xml"], "History"),
 ("Open Culture", "https://www.openculture.com", ["https://www.openculture.com/feed"], "History"),
 ("Smithsonian History", "https://www.smithsonianmag.com/category/smartnews-history-archaeology/", ["https://www.smithsonianmag.com/rss/history/"], "History"),

 ("The Kid Should See This", "https://thekidshouldseethis.com", ["https://thekidshouldseethis.com/feed"], "Science"),
 ("Phys.org", "https://phys.org", ["https://phys.org/rss-feed/"], "Science"),
 ("Biographic", "https://biographic.com", ["https://biographic.com/feed/"], "Science"),
 ("Mongabay", "https://news.mongabay.com", ["https://news.mongabay.com/feed/"], "Science"),
 ("Smithsonian Ocean", "https://ocean.si.edu", ["https://ocean.si.edu/rss.xml"], "Science"),
 ("NASA Earth Observatory", "https://science.nasa.gov/earth/earth-observatory/",
   ["https://science.nasa.gov/earth/earth-observatory/feed/", "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss"], "Science"),
 ("Audubon", "https://www.audubon.org/magazine", ["https://www.audubon.org/magazine/rss.xml", "https://www.audubon.org/rss.xml"], "Science"),
]
CATS = ["Art", "Entertainment", "Oddities", "History", "Science"]
PER_FEED = 15     # newest items read from each site or search
PER_CAT = 70      # stories kept per category (the page picks 7-8 per sheet, newest unread first)
MAX_AGE_DAYS = 21  # stories older than this are dropped (undated ones are kept)
READER_BONUS = 36 * 3600  # a story with a Reader view counts as this much newer when ranking
MAX_PER_SITE = 3  # first pass: at most this many per site, so one busy site can't take over
DROP = {"Smithsonian Ocean"}   # sources that block our servers; skipped even if they are in config.json
TOPIC_DAYS = 30   # topic searches only look at stories from the last N days
A = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "application/rss+xml, application/xml, text/xml, */*"}
AD = re.compile(r"\b(sponsored|advertorial|paid (post|partnership|content|promotion)|partner content|in partnership with|presented by|brand(ed)? content|promoted (post|content)|affiliate (links?|commission)|promo code|coupon code|discount code|deal alert|best deals?|gift guide|giveaway)\b", re.I)
SALE = re.compile(r"\(reg\.?\s*\$|\bTL;?DR\b|\blifetime (subscription|access|license|plan|deal)|one-time (purchase|payment|fee)|stacksocial|\bsave \d+%|\d+% off (with|your|at|sitewide|everything|code|when)|\d+% discount|limited[- ]time (offer|deal|price)|\bon sale\b|for just \$|only \$\d|\$\d[\d,.]* (right now|today|for life|lifetime)|\bcheck out (this|these) deals?\b|\bdeals? (of the day|roundup)\b", re.I)
DEALURL = re.compile(r"/(deals?|sponsored|promo|partner)(/|$)|[?&]utm_(medium|source)=(affiliate|sponsor)", re.I)
def is_ad(title, raw, cats="", link=""):
    body = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))[:700]
    if DEALURL.search(link or "") or re.search(r"\b(deals?|sponsored|promo(tion)?s?|shopping)\b", cats or "", re.I):
        return True
    return bool(AD.search(title + " " + body + " " + cats) or SALE.search(title + " " + body))
def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()[:60]
JUNK = re.compile(r"appeared first on|member|reader-supported|matter to you|support (independent|our)|subscribe|newsletter|sign up", re.I)
IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.I)

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

def parse_date(s):
    s = (s or "").strip()
    if not s:
        return 0
    ts = 0
    try:
        ts = int(parsedate_to_datetime(s).timestamp())
    except Exception:
        try:
            ts = int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0
    return min(ts, int(time.time()) + 3600)

def good_img(u):
    u = html.unescape((u or "").strip())
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("http://"):
        u = "https://" + u[7:]
    if not u.startswith("https://") or re.search(r"pixel|1x1|spacer|blank\.gif|/ads?/", u, re.I):
        return ""
    return u

BODY_JUNK = re.compile(r"appeared first on|read more|continue reading|subscribe|sign up for|newsletter|support (independent|our)|click here|follow us", re.I)
BODY_MAX = 4200   # characters of article text kept per story
BODY_IMGS = 5

def reader_body(raw, desc=""):
    """Reader view content, ONLY from the full text a publisher puts in its own feed (content:encoded).
    Returns [["p",text],["h",text],["i",url],...] (+ ["m",""] when cut short), or None when the feed only has an excerpt."""
    raw = re.sub(r"(?is)<(script|style|figcaption|iframe|noscript|aside|form)\b.*?</\1>", " ", raw or "")
    if len(re.sub(r"<[^>]+>", "", raw)) < 700:
        return None
    raw = re.sub(r"(?is)<img\b[^>]*?(?:data-src|src)=[\"']([^\"']+)[\"'][^>]*>", lambda m: "\n\x00" + m.group(1) + "\x00\n", raw)
    raw = re.sub(r"(?is)<h[1-6][^>]*>(.*?)</h[1-6]>", lambda m: "\n\x01" + m.group(1) + "\n", raw)
    raw = re.sub(r"(?i)</(p|div|li|blockquote|ul|ol|figure|tr)>|<br\s*/?>", "\n", raw)
    out, chars, imgs, cut = [], 0, 0, False
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("\x00"):
            u = good_img(line.strip("\x00"))
            if u and imgs < BODY_IMGS and out:
                out.append(["i", u])
                imgs += 1
            continue
        head = line.startswith("\x01")
        t = html.unescape(re.sub(r"<[^>]+>", " ", line.lstrip("\x01")))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) < (3 if head else 30) or BODY_JUNK.search(t):
            continue
        if chars + len(t) > BODY_MAX:
            room = BODY_MAX - chars
            if room > 160:
                t = t[:room].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"
                out.append(["p", t])
            cut = True
            break
        out.append(["h" if head else "p", t])
        chars += len(t)
    plain = html.unescape(re.sub(r"<[^>]+>", " ", raw))[-500:]
    preview = bool(re.search(r"(?i)read the (full )?(essay|story|article|piece)|continue reading|read the rest|read more", plain))
    texts = sum(len(v) for k, v in out if k in ("p", "h"))
    if texts < max(500, len(desc) * 2):
        return None
    while out and out[-1][0] == "i":
        out.pop()
    if cut or preview:
        out.append(["m", "preview" if preview else ""])
    return out

def find_image(it, raw):
    for tag in (MEDIA + "thumbnail", MEDIA + "content"):
        for e in it.iter(tag):
            u = e.get("url") or ""
            if u and (tag.endswith("thumbnail") or e.get("medium") == "image" or (e.get("type") or "").startswith("image") or IMG_EXT.search(u)):
                if good_img(u):
                    return good_img(u)
    for e in it.findall("enclosure"):
        if (e.get("type") or "").startswith("image") and good_img(e.get("url")):
            return good_img(e.get("url"))
    for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)", raw or "", re.I):
        if good_img(m.group(1)):
            return good_img(m.group(1))
    return ""

def parse_xml(name, data):
    root = ET.fromstring(data)
    out = []
    for it in root.findall(".//item") or root.findall(".//" + A + "entry"):
        title = clean(text(it, "title", A + "title"), 110)
        link = text(it, "link")
        if not link:
            l = it.find(A + "link")
            link = l.get("href") if l is not None else ""
        raw = text(it, "description", A + "summary", A + "content") + " " + text(it, CONTENT + "encoded")
        desc = clean(text(it, "description", A + "summary", A + "content"))
        ts = parse_date(text(it, "pubDate", "published", "updated", A + "published", A + "updated", DC + "date"))
        cats = " ".join((c.text or "") for c in it.findall("category")) + " " + " ".join((c.get("term") or "") for c in it.findall(A + "category"))
        if is_ad(title, raw, cats, link):
            continue
        if title and link.strip().startswith("http"):
            story = [name, title, desc or "Tap the button below for the full story.", link.strip(), "", find_image(it, raw), ts]
            body = reader_body(text(it, CONTENT + "encoded") or text(it, A + "content"), desc)
            if body:
                story.append(body)
            out.append(story)
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
        ts = parse_date(html.unescape(f("pubDate") or f("published") or f("updated")))
        if is_ad(title, f("description") or f("summary") or f("content"), " ".join(re.findall(r"<category[^>]*>(.*?)</category>", blk, re.S | re.I)), link):
            continue
        im = re.search(r"<media:(?:thumbnail|content)[^>]+url=[\"']([^\"']+)", blk, re.I) or re.search(r"<img[^>]+src=[\"']([^\"']+)", html.unescape(blk), re.I)
        if title and link.startswith("http"):
            out.append([name, title, desc or "Tap the button below for the full story.", link, "", good_img(im.group(1)) if im else "", ts])
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

def pick(stories):
    """Keep the newest PER_CAT stories in each category, spread across sites."""
    seen, titles, uniq = set(), set(), []
    for s in stories:
        k = norm(s[1])
        if s[3] not in seen and k not in titles:
            seen.add(s[3])
            titles.add(k)
            uniq.append(s)
    final = []
    for cat in CATS:
        # stories with a Reader view (full text in the feed) come first, newest first within each group
        pool = sorted([s for s in uniq if s[4] == cat], key=lambda s: -(s[6] + (READER_BONUS if len(s) > 7 else 0)))
        chosen, count = [], {}
        for s in pool:
            if len(chosen) < PER_CAT and count.get(s[0], 0) < MAX_PER_SITE:
                chosen.append(s)
                count[s[0]] = count.get(s[0], 0) + 1
        for s in pool:
            if len(chosen) >= PER_CAT:
                break
            if s not in chosen:
                chosen.append(s)
        final += sorted(chosen, key=lambda s: -s[6])
    return final

def og_image(url):
    pats = (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]*content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)')
    try:
        page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10).read(400000).decode("utf-8", "ignore")
        for p in pats:
            m = re.search(p, page, re.I)
            if m:
                return good_img(urllib.parse.urljoin(url, html.unescape(m.group(1))))
    except Exception:
        pass
    return ""

GN = re.compile(r"^https?://news\.google\.com/(?:rss/)?articles/([^?/#]+)")
def gn_id(url):
    m = GN.match(url or "")
    return m.group(1) if m else None

def gn_old(gid):
    """Older Google News links carry the real address inside the id itself."""
    try:
        b = base64.urlsafe_b64decode(gid + "=" * (-len(gid) % 4))
    except Exception:
        return ""
    if b.startswith(b"\x08\x13\x22"):
        b = b[3:]
    if b.endswith(b"\xd2\x01\x00"):
        b = b[:-3]
    if not b:
        return ""
    if b[0] >= 0x80 and len(b) > 1:
        n, start = (b[0] & 0x7F) | (b[1] << 7), 2
    else:
        n, start = b[0], 1
    u = b[start:start + n].decode("utf-8", "ignore")
    return u if u.startswith("http") else ""

def gn_parse_batch(text):
    parts = text.split("\n\n")
    data = json.loads(parts[1])[:-2]
    u = json.loads(data[0][2])[1]
    return u if isinstance(u, str) and u.startswith("http") else ""

def gn_new(gid):
    """Newer links need one question to Google's own page, which answers with the real address."""
    page = ""
    for base in ("https://news.google.com/rss/articles/", "https://news.google.com/articles/"):
        try:
            page = get(base + gid).decode("utf-8", "ignore")
        except Exception:
            continue
        if "data-n-a-sg" in page:
            break
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sg and ts):
        return ""
    inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]'
             % (gid, ts.group(1), sg.group(1)))
    body = ("f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", inner]]]))).encode()
    req = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": UA["User-Agent"]})
    return gn_parse_batch(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore"))

def gn_resolve(url):
    gid = gn_id(url)
    if not gid:
        return ""
    try:
        u = gn_old(gid) or gn_new(gid)
    except Exception as e:
        print("  could not resolve", url[:70], e)
        return ""
    return u if u and not gn_id(u) else ""

def og_meta(url):
    """Picture and description from an article's own page."""
    img, desc = "", ""
    try:
        page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10).read(400000).decode("utf-8", "ignore")
    except Exception:
        return "", ""
    for p in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]*content=["\']([^"\']+)',
              r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
              r'<meta[^>]+name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)'):
        m = re.search(p, page, re.I)
        if m:
            img = good_img(urllib.parse.urljoin(url, html.unescape(m.group(1))))
            if img:
                break
    for p in (r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']+)',
              r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:description["\']',
              r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)'):
        m = re.search(p, page, re.I)
        if m:
            desc = clean(m.group(1))
            if desc:
                break
    return img, desc

def load_cfg():
    try:
        return json.load(open("config.json"))
    except Exception:
        return {}

def pin_story(url, cat):
    """Read a pinned article's own page and build a story from its title, summary and picture."""
    try:
        page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12).read(500000).decode("utf-8", "ignore")
    except Exception as e:
        print("  pin failed", url, e)
        return None
    def meta(*keys):
        for k in keys:
            for p in (r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % k,
                      r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % k):
                m = re.search(p, page, re.I)
                if m and m.group(1).strip():
                    return html.unescape(m.group(1)).strip()
        return ""
    t = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    title = clean(meta("og:title", "twitter:title") or (t.group(1) if t else ""), 110)
    if not title:
        return None
    desc = clean(meta("og:description", "description", "twitter:description")) or "Tap the button below for the full story."
    site = clean(meta("og:site_name"), 40) or urllib.parse.urlparse(url).netloc.replace("www.", "")
    im = meta("og:image", "twitter:image")
    img = good_img(urllib.parse.urljoin(url, im)) if im else ""
    return [site, title, desc, url, cat, img, int(time.time())]

def main():
    cfg = load_cfg()
    sites = [(x["name"], x.get("home", ""), x.get("feeds", []), x["cat"]) for x in cfg["sites"] if x.get("cat") in CATS] if cfg.get("sites") else list(SITES)
    sites = [x for x in sites if x[0] not in DROP]
    seen_q = set()
    for t in cfg.get("topics", []):
        k = (t.get("q", "").strip().lower(), t.get("cat"))
        if k in seen_q:
            continue
        seen_q.add(k)
        if t.get("q") and t.get("cat") in CATS:
            sites.append(("Search: " + t["q"], "", ["https://news.google.com/rss/search?q=" + urllib.parse.quote('"%s" when:%dd' % (t["q"], TOPIC_DAYS)) + "&hl=en-US&gl=US&ceid=US:en"], t["cat"]))
    blocked = [b.strip().lower() for b in cfg.get("blocked", []) if b.strip()]
    stories = []
    for name, home, feeds, cat in sites:
        got = []
        for url in feeds:
            try:
                got = parse(name, get(url))
            except Exception as e:
                print("  try failed", name, url, e)
            if got:
                break
        if not got and home:
            try:
                for url in discover(home):
                    got = parse(name, get(url))
                    if got:
                        print("  found feed for", name, url)
                        break
            except Exception as e:
                print("  discovery failed", name, e)
        print(name, len(got) if got else "SKIPPED")
        for s in got:
            s[4] = cat
            if name.startswith("Search: "):
                # Google News titles end with " - Publisher": show the publisher as the source
                m = re.match(r"^(.*\S)\s+[-\u2013\u2014]\s+([^-\u2013\u2014]{2,40})$", s[1])
                if m:
                    s[1], s[0] = m.group(1), m.group(2).strip()
                    if s[2].startswith(s[1]):
                        s[2] = "Tap the button below for the full story."
        stories += got
    stories = [s for s in stories if not any(b in s[3].lower() or b in s[1].lower() for b in blocked)]
    cutoff = int(time.time()) - MAX_AGE_DAYS * 86400
    stories = [s for s in stories if s[6] == 0 or s[6] >= cutoff]
    pins = [pin_story(p["url"], p["cat"]) for p in cfg.get("pins", []) if p.get("url") and p.get("cat") in CATS]
    stories = [p for p in pins if p] + stories
    final = pick(stories)
    # Topic stories come as Google News redirects: find the real article address so we can read its picture
    cand = [s for s in final if gn_id(s[3])][:200]
    with ThreadPoolExecutor(4) as ex:
        resolved = list(ex.map(lambda s: gn_resolve(s[3]), cand))
    ok = 0
    for s, u in zip(cand, resolved):
        if u:
            s[3] = u
            ok += 1
    print("resolved", ok, "of", len(cand), "Google News links")
    final = [s for s in final if not (DEALURL.search(s[3]) or any(b in s[3].lower() for b in blocked))]
    need = [s for s in final if not gn_id(s[3]) and (not s[5] or s[2].startswith("Tap the button"))]
    with ThreadPoolExecutor(8) as ex:
        for s, (img, desc) in zip(need, ex.map(lambda s: og_meta(s[3]), need)):
            if not s[5]:
                s[5] = img
            if desc and s[2].startswith("Tap the button"):
                s[2] = desc
    for c in CATS:
        mine = [s for s in final if s[4] == c]
        print(c, len(mine), "stories,", sum(1 for s in mine if s[5]), "with pictures,", sum(1 for s in mine if len(s) > 7), "with Reader view")
    if len(final) >= 20:
        json.dump(final, open("stories.json", "w"), ensure_ascii=False, indent=1)
        print("wrote", len(final))
    else:
        print("too few stories; keeping old file")

if __name__ == "__main__":
    main()
