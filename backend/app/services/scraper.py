from __future__ import annotations

from dataclasses import dataclass
import json
import re

import httpx
from lxml import html


PORTFOLIO_URL = "https://initialized.com/portfolio"


@dataclass
class ScrapedCompany:
    name: str
    description: str | None = None
    sector: str | None = None
    website: str | None = None
    logo_url: str | None = None


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _try_extract_nextjs_data(page_html: str) -> list[ScrapedCompany]:
    tree = html.fromstring(page_html)
    script = tree.xpath("//script[@id='__NEXT_DATA__']/text()")
    if not script:
        return []

    try:
        data = json.loads(script[0])
    except Exception:
        return []

    companies: list[ScrapedCompany] = []
    seen: set[str] = set()

    # The structure may vary; we traverse common Next.js data areas.
    candidates = []
    props = data.get("props")
    if isinstance(props, dict):
        candidates.append(props)
        page_props = props.get("pageProps")
        if isinstance(page_props, dict):
            candidates.append(page_props)

    def walk(obj):
        if isinstance(obj, dict):
            # Heuristic: objects that look like company records
            name = obj.get("name")
            if isinstance(name, str) and name.strip():
                website = obj.get("website") or obj.get("url")
                description = obj.get("description")
                sector = obj.get("sector")
                logo = obj.get("logo") or obj.get("logo_url") or obj.get("logoUrl")

                if website and isinstance(website, str) and not website.startswith("http"):
                    website = None

                key = name.strip().lower()
                if key not in seen:
                    seen.add(key)
                    companies.append(
                        ScrapedCompany(
                            name=_normalize_whitespace(name),
                            description=_normalize_whitespace(description) if isinstance(description, str) and description.strip() else None,
                            sector=_normalize_whitespace(sector) if isinstance(sector, str) and sector.strip() else None,
                            website=website.strip() if isinstance(website, str) and website.strip() else None,
                            logo_url=logo.strip() if isinstance(logo, str) and logo.strip() else None,
                        )
                    )

            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for c in candidates:
        walk(c)

    return companies


def _fallback_extract_from_dom(page_html: str) -> list[ScrapedCompany]:
    tree = html.fromstring(page_html)

    companies: list[ScrapedCompany] = []
    seen: set[str] = set()

    # Heuristic: company cards are usually links with a heading text.
    for a in tree.xpath("//a[@href]"):
        href = a.get("href")
        if not href or not href.startswith("http"):
            continue

        headings = a.xpath(".//h1/text() | .//h2/text() | .//h3/text()")
        if not headings:
            continue

        name = _normalize_whitespace(headings[0])
        if not name or len(name) < 2:
            continue

        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        desc_nodes = a.xpath(".//p/text()")
        desc = _normalize_whitespace(desc_nodes[0]) if desc_nodes else None
        if desc == "":
            desc = None

        companies.append(ScrapedCompany(name=name, description=desc, website=href))

    return companies


async def scrape_initialized_portfolio() -> list[ScrapedCompany]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(PORTFOLIO_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    companies = _try_extract_nextjs_data(resp.text)
    if companies:
        return companies

    return _fallback_extract_from_dom(resp.text)
