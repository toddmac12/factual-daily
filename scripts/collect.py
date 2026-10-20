"""Collect attributed feed headlines. No generated summaries or truth scores."""
import hashlib
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/news.json"
EXCLUDE = re.compile(r"\b(opinion|editorial|commentary|analysis|perspective|podcast|horoscope|sponsored|advertorial|review|quiz)\b", re.I)
FORMAT = re.compile(r"^(watch|listen|live|in pictures|explained|fact check|how to)\b|\?|\b(what we know|what to know|why|all you need to know|blogs?)\b", re.I)


def plain(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value or "")).split())


def safe_url(value, hosts):
    try:
        p = urlsplit(value.strip())
        host = (p.hostname or "").lower()
        if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
            return None
        if not any(host == h or host.endswith("." + h) for h in hosts):
            return None
        # Feeds use tracking queries; canonical article path is sufficient here.
        return urlunsplit(("https", host, p.path, "", ""))
    except ValueError:
        return None


def parse_date(value):
    try:
        date = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            return None
    return date.astimezone(timezone.utc) if date.tzinfo else None


def iso(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_feed(raw, source, now):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations are not accepted")
    root = ET.fromstring(raw)
    rows = []
    atom = "{http://www.w3.org/2005/Atom}"
    entries = root.findall("./channel/item") if root.tag != atom + "feed" else root.findall(atom + "entry")
    if root.tag not in ("rss", atom + "feed"):
        raise ValueError("Response is not an RSS or Atom feed")
    for item in entries:
        if item.tag == atom + "entry":
            title = plain(item.findtext(atom + "title"))
            links = [x.get("href", "") for x in item.findall(atom + "link") if x.get("rel", "alternate") == "alternate"]
            link = links[0] if links else ""
            date = parse_date(item.findtext(atom + "published") or item.findtext(atom + "updated"))
            categories = " ".join(x.get("term", "") for x in item.findall(atom + "category"))
        else:
            title = plain(item.findtext("title"))
            link = item.findtext("link", "")
            date = parse_date(item.findtext("pubDate"))
            categories = " ".join(x.text or "" for x in item.findall("category"))
        url = safe_url(link, source["hosts"])
        if not title or len(title) > 400 or not url or not date:
            continue
        path = urlsplit(url).path
        if source.get("pathPrefixes") and not any(path.startswith(prefix) for prefix in source["pathPrefixes"]):
            continue
        if source["name"] == "BBC News" and not path.startswith("/news/articles/"):
            continue
        if not now - timedelta(days=7) <= date <= now:
            continue
        if EXCLUDE.search(title + " " + categories + " " + urlsplit(url).path) or FORMAT.search(title):
            continue
        rows.append({"id": hashlib.sha256(url.encode()).hexdigest()[:16], "title": title,
                     "url": url, "publishedAt": iso(date), "sourceId": source["id"],
                     "source": source["name"], "sourceUrl": source["home"],
                     "topic": source["topic"], "kind": source["kind"]})
    return rows


def fetch(source):
    request = Request(source["feed"], headers={"User-Agent": "FactualDaily/1.0 (+https://github.com/toddmac12/factual-daily)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=25) as response:
                if urlsplit(response.url).scheme != "https":
                    raise ValueError("Insecure redirect")
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Feed exceeds size limit")
                return raw
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def collect():
    now = datetime.now(timezone.utc)
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8-sig"))
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"articles": [], "sources": []}
    articles, statuses = [], []
    successes = 0
    old_status = {s["id"]: s for s in previous["sources"]}
    for source in sources:
        status = {k: source[k] for k in ("id", "name", "topic", "kind", "home", "feed")}
        status["checkedAt"] = iso(now)
        try:
            rows = parse_feed(fetch(source), source, now)
            status.update(status="ok", lastSuccessAt=iso(now), count=len(rows))
            successes += 1
            print(f'{source["id"]}: {len(rows)} eligible headlines')
        except Exception as error:
            print(f'{source["id"]}: collection failed ({type(error).__name__})', file=sys.stderr)
            # Carry only previously accepted, still-recent headlines for this source.
            rows = [a for a in previous["articles"] if a["sourceId"] == source["id"]
                    and (date := parse_date(a["publishedAt"])) and now - timedelta(days=7) <= date <= now
                    and safe_url(a["url"], source["hosts"])]
            status.update(status="unavailable", lastSuccessAt=old_status.get(source["id"], {}).get("lastSuccessAt"), count=len(rows))
        articles.extend(rows)
        statuses.append(status)
    if not successes:
        raise RuntimeError("All feeds failed; leaving the last published collection unchanged")
    unique = {a["url"]: a for a in articles}
    articles = sorted(unique.values(), key=lambda a: a["publishedAt"], reverse=True)[:160]
    if not articles:
        raise RuntimeError("No eligible headlines; leaving the last published collection unchanged")
    data = {"schemaVersion": 1, "collectedAt": iso(now), "articles": articles, "sources": statuses}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(f"Collected {len(articles)} unique headlines from {successes}/{len(sources)} feeds")


if __name__ == "__main__":
    collect()
