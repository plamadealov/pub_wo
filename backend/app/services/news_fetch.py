from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from app.config import news_api_key, news_http_user_agent
from app.schemas.news import NewsArticle, NewsBundleResponse, NewsForTicker


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_pub_date(pub: Optional[str]) -> Optional[datetime]:
    if not pub or not str(pub).strip():
        return None
    try:
        dt = parsedate_to_datetime(pub.strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def parse_google_rss_items(xml_text: str) -> List[Tuple[datetime, str, str, Optional[str]]]:
    """
    Возвращает список (published_utc, title, link, source_name) из RSS 2.0 Google News.
    """
    out: List[Tuple[datetime, str, str, Optional[str]]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        src_el = item.find("source")
        title = title_el.text if title_el is not None and title_el.text else ""
        link = link_el.text if link_el is not None and link_el.text else ""
        pub_raw = pub_el.text if pub_el is not None else None
        src = src_el.text if src_el is not None and src_el.text else None
        if not title.strip() or not link.strip():
            continue
        pdt = _parse_pub_date(pub_raw)
        if pdt is None:
            continue
        out.append((pdt, title.strip(), link.strip(), src.strip() if src else None))
    return out


def _filter_by_window(
    items: List[Tuple[datetime, str, str, Optional[str]]],
    days: int,
    limit: int = 25,
) -> List[NewsArticle]:
    cutoff = _utc_now() - timedelta(days=days)
    filtered: List[NewsArticle] = []
    seen_links = set()
    for pdt, title, link, src in sorted(items, key=lambda x: x[0], reverse=True):
        if pdt < cutoff:
            continue
        if link in seen_links:
            continue
        seen_links.add(link)
        filtered.append(
            NewsArticle(
                title=title,
                link=link,
                published_at=pdt.isoformat(),
                source=src,
            )
        )
        if len(filtered) >= limit:
            break
    return filtered


def _google_rss_url(ticker: str) -> str:
    q = f"{ticker} MOEX акции"
    qs = urlencode({"q": q, "hl": "ru", "gl": "RU", "ceid": "RU:ru"})
    return f"https://news.google.com/rss/search?{qs}"


def fetch_google_news(
    client: httpx.Client,
    ticker: str,
    days: int,
) -> List[NewsArticle]:
    url = _google_rss_url(ticker.upper())
    r = client.get(url, timeout=35.0)
    r.raise_for_status()
    raw = parse_google_rss_items(r.text)
    return _filter_by_window(raw, days)


def fetch_newsapi(
    client: httpx.Client,
    ticker: str,
    days: int,
    api_key: str,
) -> List[NewsArticle]:
    from_dt = (_utc_now() - timedelta(days=days)).date().isoformat()
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": ticker.upper(),
        "from": from_dt,
        "sortBy": "publishedAt",
        "language": "ru",
        "pageSize": 30,
        "apiKey": api_key,
    }
    r = client.get(url, params=params, timeout=35.0)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "newsapi error"))
    arts: List[NewsArticle] = []
    cutoff = _utc_now() - timedelta(days=days)
    seen = set()
    for a in data.get("articles") or []:
        link = (a.get("url") or "").strip()
        title = (a.get("title") or "").strip()
        pub = a.get("publishedAt")
        if not link or not title or link in seen:
            continue
        seen.add(link)
        try:
            pdt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if pdt.tzinfo is None:
                pdt = pdt.replace(tzinfo=timezone.utc)
            else:
                pdt = pdt.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        if pdt < cutoff:
            continue
        src_name = None
        if isinstance(a.get("source"), dict):
            src_name = a["source"].get("name")
        arts.append(
            NewsArticle(
                title=title,
                link=link,
                published_at=pdt.isoformat(),
                source=src_name,
            )
        )
        if len(arts) >= 25:
            break
    return arts


def gather_news(tickers: List[str], days: int) -> NewsBundleResponse:
    warnings: List[str] = []
    key = news_api_key()
    headers = {"User-Agent": news_http_user_agent()}
    by_ticker: List[NewsForTicker] = []
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for raw in tickers:
            t = raw.strip().upper()
            if not t:
                continue
            block = NewsForTicker(ticker=t, provider="google_rss", articles=[], error=None)
            try:
                if key:
                    try:
                        block.articles = fetch_newsapi(client, t, days, key)
                        block.provider = "newsapi"
                    except Exception as e1:
                        warnings.append(f"{t}: NewsAPI недоступен ({e1!s}), пробуем Google RSS.")
                        block.articles = fetch_google_news(client, t, days)
                        block.provider = "google_rss"
                else:
                    block.articles = fetch_google_news(client, t, days)
            except Exception as e:
                block.error = str(e)
            by_ticker.append(block)
    if not key:
        warnings.append(
            "Источник по умолчанию — RSS Google News (агрегатор). "
            "Для NewsAPI.org задайте переменную окружения NEWS_API_KEY."
        )
    return NewsBundleResponse(days=days, by_ticker=by_ticker, warnings=warnings)
