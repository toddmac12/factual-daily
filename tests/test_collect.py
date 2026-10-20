import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from scripts import collect as c

SOURCE = {"id":"test","name":"Example","topic":"World","kind":"Publisher report","home":"https://example.com/","feed":"https://example.com/rss","hosts":["example.com"]}
NOW = datetime(2026,10,19,12,tzinfo=timezone.utc)


def feed(title="A measured event occurred", date="Mon, 19 Oct 2026 11:00:00 GMT", url="https://example.com/news/1", category="News"):
    return f'<rss><channel><item><title>{title}</title><link>{url}</link><pubDate>{date}</pubDate><category>{category}</category></item></channel></rss>'.encode()


class CollectionTests(unittest.TestCase):
    def test_preserves_publisher_and_date_without_summary(self):
        row = c.parse_feed(feed(),SOURCE,NOW)[0]
        self.assertEqual(row["source"],"Example")
        self.assertEqual(row["publishedAt"],"2026-10-19T11:00:00Z")
        self.assertNotIn("summary",row)

    def test_rejects_opinion_and_analysis_metadata(self):
        for raw in (feed(title="Opinion: A decision"), feed(category="Analysis"), feed(url="https://example.com/opinion/story"), feed(title="What happened?")):
            self.assertEqual(c.parse_feed(raw,SOURCE,NOW),[])

    def test_rejects_stale_future_and_unknown_dates(self):
        for date in ("Mon, 01 Jan 2024 11:00:00 GMT","Tue, 20 Oct 2026 11:00:00 GMT","unknown", "2026-10-19T11:00:00"):
            self.assertEqual(c.parse_feed(feed(date=date),SOURCE,NOW),[])

    def test_url_allowlist_blocks_spoofs_and_script_schemes(self):
        for url in ("https://example.com.evil.org/a","javascript:alert(1)","http://example.com/a","https://example.com@evil.org/a","https://example.com:8443/a"):
            self.assertIsNone(c.safe_url(url,SOURCE["hosts"]))
        self.assertEqual(c.safe_url("https://www.example.com/a?tracking=1#x",SOURCE["hosts"]),"https://www.example.com/a")

    def test_atom_and_html_are_supported_safely(self):
        raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>&lt;b&gt;A &amp; B&lt;/b&gt;</title><link href="https://example.com/a"/><updated>2026-10-19T10:00:00Z</updated></entry></feed>'
        self.assertEqual(c.parse_feed(raw,SOURCE,NOW)[0]["title"],"A & B")

    def test_rejects_entities_and_nonfeed_responses(self):
        for raw in (b'<!DOCTYPE rss [<!ENTITY x "test">]><rss/>', b'<html/>'):
            with self.assertRaises(ValueError):
                c.parse_feed(raw,SOURCE,NOW)

    def test_release_only_sources_require_release_paths(self):
        source={**SOURCE,"pathPrefixes":["/news-release/"]}
        self.assertEqual(c.parse_feed(feed(url="https://example.com/blog/a"),source,NOW),[])
        self.assertEqual(len(c.parse_feed(feed(url="https://example.com/news-release/a"),source,NOW)),1)

    def test_all_feed_failure_leaves_previous_file_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/"sources.json").write_text(json.dumps([SOURCE]))
            output=root/"news.json"; original='{"articles":[],"sources":[]}'
            output.write_text(original)
            with patch.object(c,"ROOT",root), patch.object(c,"OUTPUT",output), patch.object(c,"fetch",side_effect=OSError("offline")):
                with self.assertRaises(RuntimeError): c.collect()
            self.assertEqual(output.read_text(),original)

    def test_partial_failure_retains_recent_but_not_old_headlines(self):
        now=datetime.now(timezone.utc)
        other={**SOURCE,"id":"other"}
        rows=[{**c.parse_feed(feed(),SOURCE,NOW)[0],"publishedAt":c.iso(now-timedelta(days=age)),"url":f"https://example.com/{age}"} for age in (1,9)]
        raw=feed(date=(now-timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S GMT"))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/"sources.json").write_text(json.dumps([SOURCE,other]))
            output=root/"news.json";output.write_text(json.dumps({"articles":rows,"sources":[]}))
            with patch.object(c,"ROOT",root),patch.object(c,"OUTPUT",output),patch.object(c,"fetch",side_effect=[OSError(),raw]),patch.object(c,"check_access",side_effect=lambda a,s,n: {**a,"access":"free","accessCheckedAt":c.iso(n)}): c.collect()
            data=json.loads(output.read_text())
            self.assertEqual(len(data["articles"]),2)
            self.assertEqual(data["sources"][0]["status"],"unavailable")
            self.assertEqual(data["sources"][1]["status"],"ok")

    def test_paywall_schema_and_visible_gates_are_rejected(self):
        source={**SOURCE,"accessPolicy":"open","bodyClasses":["article-body"]}
        body='<div class="article-body">'+'Public reporting with context. '*30+'</div>'
        self.assertTrue(c.readable_page(body,source))
        for flag in ('false','"false"'):
            schema='<script type="application/ld+json">{"@graph":[{"isAccessibleForFree":'+flag+'}]}</script>'
            self.assertFalse(c.readable_page(schema+body,source))
        for gate in ('Subscribe to continue reading','Subscription required','Sign in to read this article','Subscribers-only'):
            self.assertFalse(c.readable_page(body+'<p>'+gate+'</p>',source))

    def test_unknown_or_unreadable_sources_are_rejected(self):
        self.assertFalse(c.readable_page('<div>Public text</div>',SOURCE))
        source={**SOURCE,"accessPolicy":"open","bodyClasses":["article-body"]}
        self.assertFalse(c.readable_page('<div class="article-body">A teaser only.</div>',source))
        self.assertFalse(c.readable_page('<script>'+('x'*1000)+'</script>',source))

    def test_failed_article_access_check_omits_the_link(self):
        with patch.object(c,"urlopen",side_effect=OSError("unavailable")):
            self.assertIsNone(c.check_access({"url":"https://example.com/a"},SOURCE,NOW))


if __name__ == "__main__": unittest.main()
