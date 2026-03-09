from __future__ import annotations

import asyncio

from newspaper import Article as NewspaperArticle


def _extract_sync(url: str) -> str | None:
    article = NewspaperArticle(url)
    article.download()
    article.parse()
    text = (article.text or "").strip()
    if not text:
        return None
    return text


async def extract_article_text(url: str) -> str | None:
    return await asyncio.to_thread(_extract_sync, url)
