from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from urllib.parse import quote_plus

import feedparser
import httpx

from app.core.config import NEWSAPI_KEY


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str | None = None
    published_at: dt.datetime | None = None
    snippet: str | None = None


def _parse_newsapi_datetime(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        # example: 2026-03-09T12:34:56Z
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed
    except Exception:
        return None


def _google_struct_time_to_dt(value) -> dt.datetime | None:
    if not value:
        return None
    try:
        # time.struct_time
        return dt.datetime(*value[:6], tzinfo=dt.UTC)
    except Exception:
        return None


async def fetch_company_news_google_rss(
    company_name: str,
    max_articles: int = 5,
    when_days: int | None = 30,
) -> list[NewsArticle]:
    suffix = f" when:{when_days}d" if when_days else ""
    query = quote_plus(f"\"{company_name}\"{suffix}")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
    except Exception:
        return []

    feed = feedparser.parse(resp.text)
    items = feed.entries[:max_articles]

    articles: list[NewsArticle] = []
    for item in items:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        if not title or not link:
            continue

        source = None
        if item.get("source") and isinstance(item.get("source"), dict):
            source = item["source"].get("title")

        snippet = None
        summary = item.get("summary")
        if summary:
            snippet = str(summary).strip() or None

        published_at = _google_struct_time_to_dt(item.get("published_parsed"))

        articles.append(
            NewsArticle(
                title=title,
                url=link,
                source=source,
                published_at=published_at,
                snippet=snippet,
            )
        )

    return articles


async def fetch_company_news_newsapi(
    company_name: str,
    max_articles: int = 5,
    from_days: int = 30,
) -> list[NewsArticle]:
    if not NEWSAPI_KEY:
        return []

    now = dt.datetime.now(dt.UTC)
    from_date = (now - dt.timedelta(days=from_days)).date().isoformat()

    params = {
        "q": f"\"{company_name}\"",
        "pageSize": str(max_articles),
        "sortBy": "publishedAt",
        "language": "en",
        "from": from_date,
        "apiKey": NEWSAPI_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://newsapi.org/v2/everything", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    items = data.get("articles")
    if not isinstance(items, list):
        return []

    out: list[NewsArticle] = []
    for item in items[:max_articles]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url:
            continue
        source = None
        src = item.get("source")
        if isinstance(src, dict):
            source = src.get("name")

        out.append(
            NewsArticle(
                title=title,
                url=url,
                source=source,
                published_at=_parse_newsapi_datetime(item.get("publishedAt")),
                snippet=(item.get("description") or None),
            )
        )

    return out


def _filter_recent(articles: list[NewsArticle], max_age_days: int) -> list[NewsArticle]:
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=max_age_days)
    out: list[NewsArticle] = []
    for a in articles:
        if a.published_at is None:
            continue
        if a.published_at >= cutoff:
            out.append(a)
    return out


async def discover_company_news_with_fallback(
    company_name: str,
    max_articles: int = 5,
    primary_window_days: int = 30,
    expanded_window_days: int = 90,
) -> list[NewsArticle]:
    # Prefer very recent when possible.
    for window in (7, 14, primary_window_days):
        rss = await fetch_company_news_google_rss(company_name, max_articles=max_articles, when_days=window)
        rss_recent = _filter_recent(rss, max_age_days=window)
        if rss_recent:
            rss_recent.sort(key=lambda x: x.published_at or dt.datetime.min.replace(tzinfo=dt.UTC), reverse=True)
            return rss_recent[:max_articles]

    # RSS failed or returned nothing usable -> fallback to NewsAPI
    newsapi = await fetch_company_news_newsapi(company_name, max_articles=max_articles, from_days=primary_window_days)
    newsapi_recent = _filter_recent(newsapi, max_age_days=primary_window_days)
    if newsapi_recent:
        newsapi_recent.sort(key=lambda x: x.published_at or dt.datetime.min.replace(tzinfo=dt.UTC), reverse=True)
        return newsapi_recent[:max_articles]

    # Optional expanded window
    for window in (expanded_window_days,):
        rss = await fetch_company_news_google_rss(company_name, max_articles=max_articles, when_days=window)
        rss_recent = _filter_recent(rss, max_age_days=window)
        if rss_recent:
            rss_recent.sort(key=lambda x: x.published_at or dt.datetime.min.replace(tzinfo=dt.UTC), reverse=True)
            return rss_recent[:max_articles]

        newsapi = await fetch_company_news_newsapi(company_name, max_articles=max_articles, from_days=window)
        newsapi_recent = _filter_recent(newsapi, max_age_days=window)
        if newsapi_recent:
            newsapi_recent.sort(key=lambda x: x.published_at or dt.datetime.min.replace(tzinfo=dt.UTC), reverse=True)
            return newsapi_recent[:max_articles]

    return []
