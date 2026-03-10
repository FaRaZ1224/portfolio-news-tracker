from __future__ import annotations

from dataclasses import dataclass
import json
import re

import httpx
from lxml import html


PORTFOLIO_URLS = [
    "https://initialized.com/companies",
    "https://initialized.com/companies/",
]


@dataclass
class ScrapedCompany:
    name: str
    description: str | None = None
    sector: str | None = None
    website: str | None = None
    logo_url: str | None = None


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_asset_name(value: str) -> bool:
    v = value.strip().lower()
    if not v:
        return True
    if any(v.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
        return True
    if v.startswith("http://") or v.startswith("https://"):
        return True
    if "_carousel_" in v:
        return True
    return False


def _looks_like_category_label(value: str) -> bool:
    v = _normalize_whitespace(value).lower()
    return v in {
        "consumer",
        "healthcare",
        "enterprise",
        "marketplaces",
        "frontier tech",
        "climate",
        "fintech",
        "crypto",
        "hardware",
        "real estate",
        "exit",
    }


def _pick_logo_url(raw_logo) -> str | None:
    if isinstance(raw_logo, str) and raw_logo.strip():
        return raw_logo.strip()
    if isinstance(raw_logo, dict):
        for k in ("url", "src", "href", "logo", "logo_url", "logoUrl"):
            v = raw_logo.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _normalize_url(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://initialized.com" + u
    return u


def _try_extract_strapi_media_url(raw_logo) -> str | None:
    # Initialized appears to back this page with a CMS (Strapi-like) where logos come through as:
    # { data: { attributes: { url: "/uploads/..." } } }
    if not isinstance(raw_logo, dict):
        return None

    data = raw_logo.get("data")
    if not isinstance(data, dict):
        return None

    attrs = data.get("attributes")
    if not isinstance(attrs, dict):
        return None

    return _normalize_url(attrs.get("url"))


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
                logo = _pick_logo_url(obj.get("logo") or obj.get("logo_url") or obj.get("logoUrl"))

                if website and isinstance(website, str) and not website.startswith("http"):
                    website = None

                normalized_name = _normalize_whitespace(name)
                if _looks_like_asset_name(normalized_name) or _looks_like_category_label(normalized_name):
                    normalized_name = ""

                if not normalized_name:
                    normalized_name = ""

                key = normalized_name.strip().lower() if normalized_name else ""
                if key and key not in seen:
                    seen.add(key)
                    companies.append(
                        ScrapedCompany(
                            name=normalized_name,
                            description=_normalize_whitespace(description) if isinstance(description, str) and description.strip() else None,
                            sector=_normalize_whitespace(sector) if isinstance(sector, str) and sector.strip() else None,
                            website=website.strip() if isinstance(website, str) and website.strip() else None,
                            logo_url=logo,
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


def _extract_next_build_id(page_html: str) -> str | None:
    tree = html.fromstring(page_html)
    script = tree.xpath("//script[@id='__NEXT_DATA__']/text()")
    if not script:
        return None

    try:
        data = json.loads(script[0])
    except Exception:
        return None

    build_id = data.get("buildId")
    return build_id if isinstance(build_id, str) and build_id.strip() else None


async def _try_fetch_nextjs_data_json(client: httpx.AsyncClient, page_html: str) -> dict | None:
    build_id = _extract_next_build_id(page_html)
    if not build_id:
        return None

    candidates = [
        f"https://initialized.com/_next/data/{build_id}/companies.json",
        f"https://initialized.com/_next/data/{build_id}/companies/index.json",
    ]

    last_exc: Exception | None = None
    for url in candidates:
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else None
        except Exception as e:
            last_exc = e

    _ = last_exc
    return None


def _try_extract_from_nextjs_data_dict(data: dict) -> list[ScrapedCompany]:
    companies: list[ScrapedCompany] = []
    seen: set[str] = set()

    page_props = data.get("pageProps")
    if isinstance(page_props, dict):
        startups = page_props.get("startups")
        if isinstance(startups, dict):
            items = startups.get("data")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    attrs = item.get("attributes")
                    if not isinstance(attrs, dict):
                        continue

                    name = attrs.get("name")
                    if not isinstance(name, str) or not name.strip():
                        continue
                    normalized_name = _normalize_whitespace(name)
                    if _looks_like_asset_name(normalized_name) or _looks_like_category_label(normalized_name):
                        continue

                    website = attrs.get("website") or attrs.get("url")
                    website = website if isinstance(website, str) else None
                    website = website.strip() if isinstance(website, str) else None
                    website = website if website and website.startswith("http") else None

                    if not website:
                        website_url = attrs.get("websiteUrl")
                        website_url = website_url.strip() if isinstance(website_url, str) else None
                        website = website_url if website_url and website_url.startswith("http") else None

                    description = attrs.get("description")
                    description = _normalize_whitespace(description) if isinstance(description, str) and description.strip() else None

                    tags = attrs.get("tags")
                    sector = None
                    if isinstance(tags, dict):
                        tag_data = tags.get("data")
                        if isinstance(tag_data, list):
                            tag_names = []
                            for t in tag_data:
                                if not isinstance(t, dict):
                                    continue
                                t_attrs = t.get("attributes")
                                if not isinstance(t_attrs, dict):
                                    continue
                                tn = t_attrs.get("name")
                                if isinstance(tn, str) and tn.strip() and not _looks_like_category_label(tn):
                                    tag_names.append(_normalize_whitespace(tn))
                            if tag_names:
                                sector = ", ".join(tag_names[:3])

                    logo_url = _try_extract_strapi_media_url(attrs.get("logo"))
                    if not logo_url:
                        logo_url = _pick_logo_url(attrs.get("logo") or attrs.get("logo_url") or attrs.get("logoUrl"))
                        logo_url = _normalize_url(logo_url)

                    key = normalized_name.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    companies.append(
                        ScrapedCompany(
                            name=normalized_name,
                            description=description,
                            sector=sector,
                            website=website,
                            logo_url=logo_url,
                        )
                    )

    if companies:
        return companies

    candidates = []
    props = data.get("props")
    if isinstance(props, dict):
        candidates.append(props)
        page_props = props.get("pageProps")
        if isinstance(page_props, dict):
            candidates.append(page_props)

    def walk(obj):
        if isinstance(obj, dict):
            name = obj.get("name")
            if isinstance(name, str) and name.strip():
                website = obj.get("website") or obj.get("url")
                description = obj.get("description")
                sector = obj.get("sector")
                logo = _pick_logo_url(obj.get("logo") or obj.get("logo_url") or obj.get("logoUrl"))

                if website and isinstance(website, str) and not website.startswith("http"):
                    website = None

                normalized_name = _normalize_whitespace(name)
                if _looks_like_asset_name(normalized_name) or _looks_like_category_label(normalized_name):
                    normalized_name = ""

                key = normalized_name.strip().lower() if normalized_name else ""
                if key and key not in seen:
                    seen.add(key)
                    companies.append(
                        ScrapedCompany(
                            name=normalized_name,
                            description=_normalize_whitespace(description) if isinstance(description, str) and description.strip() else None,
                            sector=_normalize_whitespace(sector) if isinstance(sector, str) and sector.strip() else None,
                            website=website.strip() if isinstance(website, str) and website.strip() else None,
                            logo_url=logo,
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
        if not href:
            continue

        if href.startswith("/"):
            href = "https://initialized.com" + href

        if not href.startswith("http"):
            continue

        if "initialized.com/companies" not in href:
            continue

        headings = a.xpath(".//h1/text() | .//h2/text() | .//h3/text()")
        name = _normalize_whitespace(headings[0]) if headings else ""

        img_src = a.xpath(".//img/@src")
        logo_url = img_src[0].strip() if img_src and isinstance(img_src[0], str) and img_src[0].strip() else None

        if not name:
            # Logo grid case: try to get company name from image alt/aria labels.
            alt = a.xpath(".//img/@alt")
            aria = a.xpath(".//@aria-label")
            candidate = (alt[0] if alt else "") or (aria[0] if aria else "")
            name = _normalize_whitespace(candidate) if candidate else ""

        if name and (_looks_like_asset_name(name) or _looks_like_category_label(name)):
            name = ""

        if not name:
            continue
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

        companies.append(ScrapedCompany(name=name, description=desc, website=href, logo_url=logo_url))

    return companies


async def scrape_initialized_portfolio() -> list[ScrapedCompany]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = None
        last_exc: Exception | None = None
        for url in PORTFOLIO_URLS:
            try:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                break
            except Exception as e:
                last_exc = e
                resp = None

        if resp is None:
            raise last_exc or RuntimeError("Failed to fetch portfolio page")

        next_data_json = await _try_fetch_nextjs_data_json(client, resp.text)

    nextjs_companies = _try_extract_nextjs_data(resp.text)
    data_json_companies = _try_extract_from_nextjs_data_dict(next_data_json) if isinstance(next_data_json, dict) else []
    dom_companies = _fallback_extract_from_dom(resp.text)

    by_name: dict[str, ScrapedCompany] = {}

    def merge_into(existing: ScrapedCompany, incoming: ScrapedCompany) -> ScrapedCompany:
        if not existing.description and incoming.description:
            existing.description = incoming.description
        if not existing.sector and incoming.sector:
            existing.sector = incoming.sector
        if not existing.website and incoming.website:
            existing.website = incoming.website
        if not existing.logo_url and incoming.logo_url:
            existing.logo_url = incoming.logo_url
        return existing

    for c in nextjs_companies + data_json_companies + dom_companies:
        key = c.name.strip().lower() if c.name else ""
        if not key:
            continue
        if key not in by_name:
            by_name[key] = c
            continue
        by_name[key] = merge_into(by_name[key], c)

    return list(by_name.values())
