from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, HttpUrl


class ArticleOut(BaseModel):
    id: int
    title: str
    url: str
    source: str | None = None
    published_at: dt.datetime | None = None
    snippet: str | None = None
    content_text: str | None = None
    discovered_at: dt.datetime | None = None
    is_new: bool | None = None


class SummaryOut(BaseModel):
    summary_text: str
    generated_at: dt.datetime


class CompanyOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    sector: str | None = None
    website: str | None = None
    logo_url: str | None = None
    summary: SummaryOut | None = None
    articles: list[ArticleOut] = []


class RefreshResponse(BaseModel):
    company_id: int
    articles_added: int
    summary_generated: bool
