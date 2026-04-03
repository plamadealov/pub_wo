from datetime import datetime, timedelta, timezone

from app.services.news_fetch import _filter_by_window, parse_google_rss_items


def test_parse_google_rss_minimal() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
    <item>
      <title>Test headline</title>
      <link>https://example.com/a</link>
      <pubDate>Fri, 03 Apr 2026 10:00:00 GMT</pubDate>
      <source url="https://ex.com">Example</source>
    </item>
    </channel></rss>"""
    rows = parse_google_rss_items(xml)
    assert len(rows) == 1
    assert rows[0][1] == "Test headline"
    assert rows[0][3] == "Example"


def test_filter_by_window() -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    items = [
        (now, "n1", "https://a", None),
        (old, "old", "https://b", None),
    ]
    out = _filter_by_window(items, days=10, limit=10)
    assert len(out) == 1
    assert out[0].title == "n1"
