from __future__ import annotations

import datetime as dt

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import selectinload

load_dotenv()

from app.core.config import (
    CORS_ALLOW_ORIGINS,
    NEWS_FETCH_MAX_ARTICLES_PER_COMPANY,
    NEWS_RECENCY_DAYS_EXPANDED,
    NEWS_RECENCY_DAYS_PRIMARY,
)
from app.db import Base, engine, get_db_session
from app.models import Article, Company, Summary
from app.schemas import CompanyOut, RefreshResponse
from app.services.extractor import extract_article_text
from app.services.news import discover_company_news_with_fallback
from app.services.scraper import scrape_initialized_portfolio
from app.services.summarizer import generate_company_summary

app = FastAPI(title="Initialized Portfolio News Tracker")

_allow_all_origins = (not CORS_ALLOW_ORIGINS) or ("*" in CORS_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all_origins else CORS_ALLOW_ORIGINS,
    allow_credentials=False if _allow_all_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/scrape-portfolio")
async def scrape_portfolio():
    try:
        scraped = await scrape_initialized_portfolio()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e.__class__.__name__}")
    if not scraped:
        raise HTTPException(status_code=502, detail="No companies scraped")

    created = 0
    updated = 0

    with get_db_session() as db:
        for sc in scraped:
            existing = db.scalar(select(Company).where(Company.name == sc.name))
            if existing:
                existing.description = sc.description
                existing.website = sc.website
                existing.sector = sc.sector
                existing.logo_url = sc.logo_url
                updated += 1
            else:
                db.add(
                    Company(
                        name=sc.name,
                        description=sc.description,
                        sector=sc.sector,
                        website=sc.website,
                        logo_url=sc.logo_url,
                    )
                )
                created += 1
        db.commit()

    return {"created": created, "updated": updated}


@app.get("/companies", response_model=list[CompanyOut])
def get_companies():
    with get_db_session() as db:
        companies = db.scalars(
            select(Company)
            .options(
                selectinload(Company.articles),
                selectinload(Company.summary),
            )
            .order_by(Company.name.asc())
        ).all()
        out: list[CompanyOut] = []
        for c in companies:
            summary = None
            if c.summary:
                summary = {"summary_text": c.summary.summary_text, "generated_at": c.summary.generated_at}

            articles = []
            for a in sorted(c.articles, key=lambda x: (x.published_at or dt.datetime.min.replace(tzinfo=dt.UTC)), reverse=True):
                articles.append(
                    {
                        "id": a.id,
                        "title": a.title,
                        "url": a.url,
                        "source": a.source,
                        "published_at": a.published_at,
                        "snippet": a.snippet,
                        "content_text": a.content_text,
                        "discovered_at": a.discovered_at,
                        "is_new": a.is_new,
                    }
                )

            out.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "sector": c.sector,
                    "website": c.website,
                    "logo_url": c.logo_url,
                    "summary": summary,
                    "articles": articles,
                }
            )
        return out


@app.post("/refresh/{company_id}", response_model=RefreshResponse)
async def refresh_company(company_id: int):
    with get_db_session() as db:
        company = db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        now = dt.datetime.now(dt.UTC)
        added = 0
        summary_generated = False
        summary_error: str | None = None

        try:
            discovered = await discover_company_news_with_fallback(
                company.name,
                max_articles=NEWS_FETCH_MAX_ARTICLES_PER_COMPANY,
                primary_window_days=NEWS_RECENCY_DAYS_PRIMARY,
                expanded_window_days=NEWS_RECENCY_DAYS_EXPANDED,
            )
        except Exception:
            discovered = []

        # Insert newly discovered articles, skip existing URLs.
        for n in discovered:
            try:
                exists = db.scalar(select(Article).where(Article.company_id == company.id, Article.url == n.url))
                if exists:
                    # Update metadata if needed, but do not relabel as new.
                    if not exists.source and n.source:
                        exists.source = n.source
                    if not exists.published_at and n.published_at:
                        exists.published_at = n.published_at
                    if not exists.snippet and n.snippet:
                        exists.snippet = n.snippet
                    continue

                is_new = False
                if n.published_at and (now - n.published_at) <= dt.timedelta(hours=48):
                    is_new = True

                db.add(
                    Article(
                        company_id=company.id,
                        title=n.title,
                        url=n.url,
                        source=n.source,
                        published_at=n.published_at,
                        snippet=n.snippet,
                        discovered_at=now,
                        is_new=is_new,
                    )
                )
                added += 1
            except Exception:
                continue

        db.commit()

        # Extract main text for the 2–3 most recent articles (prefer newest by published_at).
        refreshed_articles = db.scalars(
            select(Article)
            .where(Article.company_id == company.id)
            .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
        ).all()

        articles_for_summary = refreshed_articles[:3]
        for a in articles_for_summary:
            if a.content_text:
                continue
            try:
                text = await extract_article_text(a.url)
                if text:
                    a.content_text = text[:3000]
            except Exception:
                a.content_text = None

        # Update is_new for articles discovered in last 24h (only for newly inserted rows).
        # We avoid relabeling old articles as new by not touching existing URLs above.
        for a in refreshed_articles:
            if a.discovered_at and (now - a.discovered_at) <= dt.timedelta(hours=24):
                a.is_new = True

        db.commit()

        # Generate summary. If no usable articles, store safe fallback.
        try:
            usable = [a for a in articles_for_summary if a.title and a.url]
            if not usable:
                summary_text = "No clear recent company announcements were reported in the available articles."
            else:
                summary_text = generate_company_summary(
                    company.name,
                    [
                        {
                            "title": a.title,
                            "snippet": a.snippet,
                            "source": a.source,
                            "published_at": a.published_at,
                            "content_text": a.content_text,
                        }
                        for a in usable
                    ],
                )
            summary_generated = True
        except Exception as e:
            summary_text = "No clear recent company announcements were reported in the available articles."
            summary_error = f"{e.__class__.__name__}: {e}"
            summary_generated = False

        try:
            if company.summary:
                company.summary.summary_text = summary_text
                company.summary.generated_at = now
            else:
                db.add(Summary(company_id=company.id, summary_text=summary_text))
            db.commit()
        except Exception as e:
            db.rollback()
            if not summary_error:
                summary_error = f"DBWriteError: {e.__class__.__name__}: {e}"

        return {
            "company_id": company.id,
            "articles_added": added,
            "summary_generated": summary_generated,
            "summary_text": summary_text,
            "error": summary_error,
        }


@app.post("/refresh-all")
async def refresh_all():
    with get_db_session() as db:
        company_ids = db.scalars(select(Company.id)).all()

    results = []
    for cid in company_ids:
        try:
            results.append(await refresh_company(cid))
        except Exception:
            results.append({"company_id": cid, "articles_added": 0, "summary_generated": False})
    return {"count": len(results), "results": results}
